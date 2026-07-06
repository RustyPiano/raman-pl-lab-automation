import csv
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from lab_auto.config import WorkflowConfig
from lab_auto.devices.base import close_all_quietly
from lab_auto.devices.dfield_validation import validate_dfield_capture_args
from lab_auto.devices.optics_validation import validate_zolix_optics
from lab_auto.devices.light import ManualLight
from lab_auto.devices.simulated import SimulatedCamera, SimulatedSpectrometer
from lab_auto.devices.zolix_spectrometer import direct_to_front_bool
from lab_auto.errors import ConfigError, SafetyError, WorkflowCancelled
from lab_auto.logging import append_run_log
from lab_auto.processing.background import subtract_background
from lab_auto.workflow.data import CaptureFrame, SpectrumData


@dataclass
class RamanWorkflow:
    config: WorkflowConfig
    dry: bool
    camera: object
    spectrometer: object
    light: object
    runtime_mode: str

    @classmethod
    def dry_run(cls, config: WorkflowConfig) -> "RamanWorkflow":
        return cls(config, True, SimulatedCamera(), SimulatedSpectrometer(), ManualLight(manual=True), "dry_run")

    @classmethod
    def simulated(cls, config: WorkflowConfig) -> "RamanWorkflow":
        return cls(config, False, SimulatedCamera(), SimulatedSpectrometer(), ManualLight(manual=True), "simulated")

    @classmethod
    def real(cls, config: WorkflowConfig, *, stage, spectrometer, camera, light) -> "RamanWorkflow":
        workflow = cls(config, False, camera, spectrometer, light, "real")
        workflow.stage = stage
        return workflow

    def close(self) -> None:
        close_all_quietly((getattr(self, "stage", None), self.spectrometer, self.camera, self.light))

    def measure_single_point(self, *, require_confirmation: bool) -> list[str]:
        self.validate_single_point_config()
        actions = [
            "devices_check",
            f"set_entrance_port:{self.config.optics.entrance_port}",
            f"set_exit_port:{self.config.optics.exit_port}",
            f"set_grating:{self.config.optics.grating}",
            f"move_wavelength_nm:{self.config.optics.center_wavelength_nm}",
            f"set_slit_width_um:{self.config.optics.slit_width_um}",
        ]
        if self.config.acquisition.subtract_background:
            actions.extend([self.light.require_off_confirmation(), "capture_background"])
        actions.extend([self.light.require_on_confirmation(), "capture_sample"])
        if self.config.acquisition.subtract_background:
            actions.append("subtract_background")
        actions.append("save_outputs")
        return actions

    def validate_single_point_config(self) -> None:
        direct_to_front_bool(self.config.optics.entrance_port)
        direct_to_front_bool(self.config.optics.exit_port)
        validate_zolix_optics(
            grating=self.config.optics.grating,
            wavelength_nm=self.config.optics.center_wavelength_nm,
            slit_um=self.config.optics.slit_width_um,
        )
        if self.config.acquisition.read_mode != "fvb":
            raise ConfigError("single-point workflow requires read_mode=fvb")
        validate_dfield_capture_args(
            read_mode=self.config.acquisition.read_mode,
            exposure_ms=self.config.acquisition.exposure_ms,
            gain=self.config.acquisition.gain,
            frames=self.config.acquisition.frames,
        )

    def _frame_to_spectrum(self, frame: CaptureFrame) -> SpectrumData:
        warnings: list[str] = []
        try:
            x = self.spectrometer.pixels_to_waves(
                turret=0,
                grating=self.config.optics.grating,
                center_wavelength_nm=self.config.optics.center_wavelength_nm,
                width=int(frame.metadata.get("detector_width", frame.width)),
                count=len(frame.values),
                bin_x=frame.bin_x,
            )
        except Exception:
            x = []
            warnings.append("wavelength calibration failed; using pixel_index")
        if len(x) == len(frame.values):
            x_axis_type = "wavelength_nm"
        else:
            x_axis_type = "pixel_index"
            x = list(range(len(frame.values)))
            if not warnings:
                warnings.append("wavelength calibration unavailable; using pixel_index")
        saturated = frame.saturated if len(frame.saturated) == len(frame.values) else [False for _ in frame.values]
        if any(saturated):
            warnings.append("saturated pixels detected")
        metadata = {
            "read_mode": self.config.acquisition.read_mode,
            "bin_x": frame.bin_x,
            "bin_y": frame.bin_y,
            "roi": frame.roi,
            "detector_width": int(frame.metadata.get("detector_width", frame.width)),
            "detector_height": int(frame.metadata.get("detector_height", frame.height)),
            "grating": self.config.optics.grating,
            "center_wavelength_nm": self.config.optics.center_wavelength_nm,
            "slit_width_um": self.config.optics.slit_width_um,
            "saturated_count": sum(1 for value in saturated if value),
            "saturation_threshold": frame.saturation_threshold,
            "raw_frames_count": frame.raw_frames_count,
            "warnings": warnings,
        }
        return SpectrumData(
            x_axis_type=x_axis_type,
            x=x,
            intensity_raw=[float(value) for value in frame.values],
            intensity_background=None,
            intensity_corrected=None,
            saturated=saturated,
            metadata=metadata,
        )

    def run_single_point(
        self,
        *,
        require_confirmation: bool,
        should_cancel: Callable[[], bool] | None = None,
    ) -> Path:
        def _check_cancel() -> None:
            if should_cancel is not None and should_cancel():
                raise WorkflowCancelled("single-point workflow cancelled by stop request")

        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("🔬 开始单点光谱采集流程")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        print("\n[1/8] 验证配置参数...")
        self.validate_single_point_config()
        print("✓ 配置验证通过")
        # Checkpoint: cancel here is before any hardware/laser action and before the
        # run directory is created — nothing to make safe, just abort cleanly.
        _check_cancel()

        timestamp = datetime.now(timezone.utc)
        run_dir = self.config.output.directory / f"{timestamp.strftime('%Y%m%d-%H%M%S-%f')}-{self.config.sample.id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        print(f"✓ 输出目录: {run_dir}")

        laser_off_after_sample = False
        try:
            # Checkpoint: cancel from here on routes through the except path below,
            # which forces the laser off before re-raising.
            _check_cancel()
            print("\n[2/8] 配置光谱仪...")
            print(f"  - 光栅: {self.config.optics.grating}")
            print(f"  - 中心波长: {self.config.optics.center_wavelength_nm} nm")
            print(f"  - 狭缝宽度: {self.config.optics.slit_width_um} μm")
            self._configure_spectrometer()
            print("✓ 光谱仪配置完成")

            background_frame = None
            if self.config.acquisition.subtract_background:
                print("\n[3/8] 采集背景光谱...")
                print(f"  - 曝光时间: {self.config.acquisition.exposure_ms} ms")
                print(f"  - 帧数: {self.config.acquisition.frames}")
                _check_cancel()
                self._confirm_laser_off(require_confirmation=require_confirmation or self.runtime_mode == "real")
                print("  > 正在采集背景 (激光关闭)...")
                background_frame = self.camera.capture(
                    read_mode=self.config.acquisition.read_mode,
                    exposure_ms=self.config.acquisition.exposure_ms,
                    gain=self.config.acquisition.gain,
                    frames=self.config.acquisition.frames,
                )
                print("✓ 背景采集完成")
            else:
                print("\n[3/8] 跳过背景采集 (未启用背景扣除)")

            print("\n[4/8] 采集样品光谱...")
            print(f"  - 曝光时间: {self.config.acquisition.exposure_ms} ms")
            print(f"  - 帧数: {self.config.acquisition.frames}")
            # Checkpoint: last chance before the laser is switched ON.
            _check_cancel()
            self._confirm_laser_on(require_confirmation=require_confirmation or self.runtime_mode == "real")
            print("  > 正在采集样品光谱 (激光开启)...")
            _check_cancel()
            sample_frame = self.camera.capture(
                read_mode=self.config.acquisition.read_mode,
                exposure_ms=self.config.acquisition.exposure_ms,
                gain=self.config.acquisition.gain,
                frames=self.config.acquisition.frames,
            )
            print("✓ 样品采集完成")

            if self.runtime_mode == "real":
                self._confirm_laser_off(require_confirmation=require_confirmation or self.runtime_mode == "real")
                laser_off_after_sample = True
                print("✓ 激光已关闭")

            print("\n[5/8] 处理光谱数据...")
            background = self._frame_to_spectrum(background_frame) if background_frame is not None else None
            raw = self._frame_to_spectrum(sample_frame)
            if background is not None and (raw.x_axis_type == "pixel_index" or background.x_axis_type == "pixel_index"):
                background = self._as_pixel_index(background)
                raw = self._as_pixel_index(raw)
            print("✓ 光谱数据处理完成")

            print("\n[6/8] 背景扣除...")
            corrected = subtract_background(raw, background) if background is not None else None
            if corrected is not None:
                print("✓ 背景扣除完成")
            else:
                print("⊘ 未执行背景扣除")

            warnings = list(
                dict.fromkeys((background.metadata.get("warnings", []) if background is not None else []) + raw.metadata.get("warnings", []))
            )

            print("\n[7/8] 保存数据文件...")
            self._write_raw(run_dir / "raw.csv", raw)
            print("  ✓ raw.csv")
            if background is not None and corrected is not None:
                self._write_background(run_dir / "background.csv", background)
                print("  ✓ background.csv")
                self._write_corrected(run_dir / "corrected.csv", corrected)
                print("  ✓ corrected.csv")
            self._write_metadata(run_dir / "metadata.json", timestamp=timestamp, raw=raw, sample_frame=sample_frame, warnings=warnings)
            print("  ✓ metadata.json")

            print("\n[8/8] 记录运行日志...")
            append_run_log(run_dir / "run.log", "single_point_complete")
            print("✓ 运行日志已记录")

            print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            print("✅ 单点光谱采集完成!")
            if warnings:
                print("\n⚠️  警告信息:")
                for w in warnings:
                    print(f"  - {w}")
            print(f"\n📁 数据已保存至: {run_dir}")
            print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
        except Exception:
            print("\n❌ 采集过程出错!")
            if not laser_off_after_sample:
                self._confirm_laser_off_after_failure(require_confirmation=require_confirmation or self.runtime_mode == "real")
            raise
        return run_dir

    def _write_metadata(self, path: Path, *, timestamp: datetime, raw: SpectrumData, sample_frame: CaptureFrame, warnings: list[str]) -> None:
        path.write_text(
            json.dumps(
                {
                    "timestamp": timestamp.isoformat(),
                    "sample_id": self.config.sample.id,
                    "operator": self.config.sample.operator,
                    "x_axis_type": raw.x_axis_type,
                    "runtime_mode": self.runtime_mode,
                    "stage_position_um": self._stage_position(),
                    "devices": {
                        "stage": self._stage_metadata(),
                        "spectrometer": self._device_status(self.spectrometer, fallback_type="spectrometer"),
                        "camera": self._device_status(self.camera, fallback_type="camera"),
                    },
                    "spectrometer": {
                        "grating": self.config.optics.grating,
                        "center_wavelength_nm": self.config.optics.center_wavelength_nm,
                        "slit_width_um": self.config.optics.slit_width_um,
                        "entrance_port": self.config.optics.entrance_port,
                        "exit_port": self.config.optics.exit_port,
                    },
                    "camera": {
                        "exposure_ms": self.config.acquisition.exposure_ms,
                        "gain": self.config.acquisition.gain,
                        "read_mode": self.config.acquisition.read_mode,
                        "frames": self.config.acquisition.frames,
                        "bin_x": sample_frame.bin_x,
                        "bin_y": sample_frame.bin_y,
                        "roi": sample_frame.roi,
                        "saturated_count": raw.metadata["saturated_count"],
                        "saturation_threshold": raw.metadata["saturation_threshold"],
                        "raw_frames_count": raw.metadata["raw_frames_count"],
                    },
                    "background_subtraction": {
                        "enabled": self.config.acquisition.subtract_background,
                        "wavelength_tolerance_nm": 1e-6,
                    },
                    "warnings": warnings,
                    "errors": [],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _confirm_laser_off(self, *, require_confirmation: bool) -> None:
        confirm = getattr(self.light, "confirm_laser_off", None)
        if confirm is not None:
            confirm(require_confirmation=require_confirmation)
        if getattr(self.light, "laser_state", "off_confirmed") != "off_confirmed":
            raise ConfigError("background capture requires laser_state=off_confirmed")

    def _as_pixel_index(self, spectrum: SpectrumData) -> SpectrumData:
        if spectrum.x_axis_type == "pixel_index":
            return spectrum
        return replace(spectrum, x_axis_type="pixel_index", x=list(range(len(spectrum.intensity_raw))))

    def _confirm_laser_on(self, *, require_confirmation: bool) -> None:
        confirm = getattr(self.light, "confirm_laser_on", None)
        if confirm is not None:
            confirm(require_confirmation=require_confirmation)
        if getattr(self.light, "laser_state", "on_confirmed") != "on_confirmed":
            raise ConfigError("sample capture requires laser_state=on_confirmed")

    def _confirm_laser_off_after_failure(self, *, require_confirmation: bool) -> None:
        try:
            self._confirm_laser_off(require_confirmation=require_confirmation)
        except Exception as exc:
            # On real hardware a failed emergency laser-off is more urgent than the
            # error we're already handling: escalate to SafetyError (the original
            # exception is preserved as __context__) so the operator knows the laser
            # may still be ON. Dry-run/simulated has nothing physical to make safe.
            if self.runtime_mode == "real":
                raise SafetyError("laser-off could not be confirmed after a failure; laser may still be ON") from exc

    def _configure_spectrometer(self) -> None:
        initialize = getattr(self.spectrometer, "initialize", None)
        if initialize is not None:
            initialize(entrance_port=self.config.optics.entrance_port, exit_port=self.config.optics.exit_port)
        set_grating = getattr(self.spectrometer, "set_grating", None)
        if set_grating is not None:
            set_grating(self.config.optics.grating)
        move_to_wavelength_nm = getattr(self.spectrometer, "move_to_wavelength_nm", None)
        if move_to_wavelength_nm is not None:
            move_to_wavelength_nm(self.config.optics.center_wavelength_nm)
        set_slit_width_um = getattr(self.spectrometer, "set_slit_width_um", None)
        if set_slit_width_um is not None:
            set_slit_width_um(self.config.optics.slit_width_um)

    def _stage_position(self) -> dict | None:
        stage = getattr(self, "stage", None)
        ledger = getattr(stage, "ledger", None)
        positions = getattr(ledger, "position_um", None)
        if not isinstance(positions, dict) or not positions:
            return None
        return {axis: value for axis, value in positions.items()}

    def _stage_metadata(self) -> dict | None:
        stage = getattr(self, "stage", None)
        if stage is None:
            return None
        identify = getattr(stage, "identify", None)
        if identify is None:
            return {"type": stage.__class__.__name__}
        try:
            result = identify()
        except Exception as exc:
            return {"type": stage.__class__.__name__, "status_error": str(exc)}
        return result if isinstance(result, dict) else {"type": stage.__class__.__name__, "status": result}

    def _device_status(self, device: object, *, fallback_type: str) -> dict:
        status = getattr(device, "status", None)
        if status is None:
            return {"type": fallback_type}
        try:
            result = status()
        except Exception as exc:
            return {"type": fallback_type, "status_error": str(exc)}
        if isinstance(result, dict):
            return result
        return {"type": fallback_type, "status": result}

    def _write_raw(self, path: Path, spectrum: SpectrumData) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if spectrum.x_axis_type == "wavelength_nm":
                writer.writerow(["pixel_index", "wavelength_nm", "intensity_raw", "saturated"])
                for index, (wave, value, saturated) in enumerate(zip(spectrum.x, spectrum.intensity_raw, spectrum.saturated, strict=True)):
                    writer.writerow([index, wave, value, str(saturated).lower()])
            else:
                writer.writerow(["pixel_index", "intensity_raw", "saturated"])
                for index, (value, saturated) in enumerate(zip(spectrum.intensity_raw, spectrum.saturated, strict=True)):
                    writer.writerow([index, value, str(saturated).lower()])

    def _write_background(self, path: Path, spectrum: SpectrumData) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if spectrum.x_axis_type == "wavelength_nm":
                writer.writerow(["pixel_index", "wavelength_nm", "intensity_background", "saturated"])
                for index, (wave, value, saturated) in enumerate(zip(spectrum.x, spectrum.intensity_raw, spectrum.saturated, strict=True)):
                    writer.writerow([index, wave, value, str(saturated).lower()])
            else:
                writer.writerow(["pixel_index", "intensity_background", "saturated"])
                for index, (value, saturated) in enumerate(zip(spectrum.intensity_raw, spectrum.saturated, strict=True)):
                    writer.writerow([index, value, str(saturated).lower()])

    def _write_corrected(self, path: Path, spectrum: SpectrumData) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            background_saturated = spectrum.background_saturated or [False for _ in spectrum.x]
            if spectrum.x_axis_type == "wavelength_nm":
                writer.writerow(
                    [
                        "pixel_index",
                        "wavelength_nm",
                        "intensity_raw",
                        "intensity_background",
                        "intensity_corrected",
                        "saturated_raw",
                        "saturated_background",
                    ]
                )
                for index, wave in enumerate(spectrum.x):
                    writer.writerow(
                        [
                            index,
                            wave,
                            spectrum.intensity_raw[index],
                            spectrum.intensity_background[index],
                            spectrum.intensity_corrected[index],
                            str(spectrum.saturated[index]).lower(),
                            str(background_saturated[index]).lower(),
                        ]
                    )
            else:
                writer.writerow(["pixel_index", "intensity_raw", "intensity_background", "intensity_corrected", "saturated_raw", "saturated_background"])
                for index in range(len(spectrum.x)):
                    writer.writerow(
                        [
                            index,
                            spectrum.intensity_raw[index],
                            spectrum.intensity_background[index],
                            spectrum.intensity_corrected[index],
                            str(spectrum.saturated[index]).lower(),
                            str(background_saturated[index]).lower(),
                        ]
                    )
