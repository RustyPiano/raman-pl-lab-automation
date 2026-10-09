import csv
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from lab_auto import __version__
from lab_auto.config import WorkflowConfig
from lab_auto.devices.base import close_all_quietly
from lab_auto.devices.dfield_validation import validate_dfield_capture_args
from lab_auto.devices.optics_validation import validate_zolix_optics
from lab_auto.devices.light import ManualLight
from lab_auto.devices.simulated import SimulatedCamera, SimulatedSpectrometer
from lab_auto.devices.zolix_spectrometer import direct_to_front_bool
from lab_auto.errors import ConfigError, DeviceError, SafetyError, WorkflowCancelled
from lab_auto.processing.background import subtract_background
from lab_auto.storage import append_run_log, write_json
from lab_auto.workflow.data import CaptureFrame, SpectrumData


def read_single_point_result(run_dir: str | Path) -> dict:
    """Read the files written by ``run_single_point`` into the API result shape."""
    run_dir = Path(run_dir)

    def _column(path: Path, value_key: str) -> tuple[list[float | int], list[float], str]:
        x: list[float | int] = []
        values: list[float] = []
        x_axis_type = "pixel_index"
        if not path.exists():
            return x, values, x_axis_type
        with path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row.get("wavelength_nm") not in (None, ""):
                    x_axis_type = "wavelength_nm"
                    x.append(float(row["wavelength_nm"]))
                else:
                    x.append(int(row["pixel_index"]))
                values.append(float(row[value_key]))
        return x, values, x_axis_type

    x, raw, x_axis_type = _column(run_dir / "raw.csv", "intensity_raw")
    _, corrected, _ = _column(run_dir / "corrected.csv", "intensity_corrected")
    metadata_path = run_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    raw_warnings = metadata.get("warnings", [])
    warnings = (
        [warning for warning in raw_warnings if isinstance(warning, str)]
        if isinstance(raw_warnings, list)
        else []
    )
    metadata["warnings"] = warnings
    return {
        "x": x,
        "x_axis_type": x_axis_type,
        "wavelengths": x if x_axis_type == "wavelength_nm" else None,
        "spectrum": {"raw": raw, "corrected": corrected or None},
        "metadata": metadata,
        "warnings": warnings,
    }


def _read_status(read) -> dict:
    # 只为写入元数据而读取的设备状态：读取失败时记录原因，不让已经采完的测量失败
    # （WayneLabs identify 首响应分包问题尚未修复）
    try:
        return read()
    except Exception as exc:
        return {"status_error": str(exc)}


@dataclass
class RamanWorkflow:
    config: WorkflowConfig
    dry: bool
    camera: object
    spectrometer: object
    light: object
    runtime_mode: str
    stage: object = None
    devices_snapshot: dict | None = None

    @classmethod
    def dry_run(cls, config: WorkflowConfig) -> "RamanWorkflow":
        return cls(config, True, SimulatedCamera(), SimulatedSpectrometer(), ManualLight(), "dry_run")

    @classmethod
    def simulated(cls, config: WorkflowConfig) -> "RamanWorkflow":
        light = ManualLight()
        return cls(config, False, SimulatedCamera(light), SimulatedSpectrometer(), light, "simulated")

    @classmethod
    def real(cls, config: WorkflowConfig, *, stage, spectrometer, camera, light) -> "RamanWorkflow":
        return cls(config, False, camera, spectrometer, light, "real", stage=stage)

    def close(self) -> None:
        close_all_quietly((self.stage, self.spectrometer, self.camera, self.light))

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
        detector_width = int(frame.metadata.get("detector_width", frame.width))
        x = self.spectrometer.pixels_to_waves(
            turret=0,
            grating=self.config.optics.grating,
            center_wavelength_nm=self.config.optics.center_wavelength_nm,
            width=detector_width,
            count=len(frame.values),
            bin_x=frame.bin_x,
        )
        if len(x) != len(frame.values):
            raise DeviceError(f"wavelength calibration returned {len(x)} values for {len(frame.values)} pixels")
        if len(frame.saturated) != len(frame.values):
            raise DeviceError("saturation flags do not match the captured pixel count")
        warnings = ["saturated pixels detected"] if any(frame.saturated) else []
        metadata = {
            "read_mode": self.config.acquisition.read_mode,
            "bin_x": frame.bin_x,
            "bin_y": frame.bin_y,
            "roi": frame.roi,
            "detector_width": detector_width,
            "detector_height": int(frame.metadata.get("detector_height", frame.height)),
            "grating": self.config.optics.grating,
            "center_wavelength_nm": self.config.optics.center_wavelength_nm,
            "slit_width_um": self.config.optics.slit_width_um,
            "saturated_count": sum(frame.saturated),
            "saturation_threshold": frame.saturation_threshold,
            "raw_frames_count": frame.raw_frames_count,
            "warnings": warnings,
        }
        return SpectrumData(
            x_axis_type="wavelength_nm",
            x=x,
            intensity_raw=[float(value) for value in frame.values],
            intensity_background=None,
            intensity_corrected=None,
            saturated=frame.saturated,
            metadata=metadata,
        )

    def _capture(self, should_cancel):
        return self.camera.capture(
            read_mode=self.config.acquisition.read_mode,
            exposure_ms=self.config.acquisition.exposure_ms,
            gain=self.config.acquisition.gain,
            frames=self.config.acquisition.frames,
            should_cancel=should_cancel,
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

        confirm = require_confirmation or self.runtime_mode == "real"

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
            write_json(run_dir / "metadata.json", {**self._run_metadata(timestamp), "status": "running"})
            append_run_log(run_dir / "run.log", f"{timestamp.isoformat()} single_point_started")
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
                self._confirm_laser_off(require_confirmation=confirm)
                print("  > 正在采集背景 (激光关闭)...")
                background_frame = self._capture(should_cancel)
                print("✓ 背景采集完成")
            else:
                print("\n[3/8] 跳过背景采集 (未启用背景扣除)")

            print("\n[4/8] 采集样品光谱...")
            print(f"  - 曝光时间: {self.config.acquisition.exposure_ms} ms")
            print(f"  - 帧数: {self.config.acquisition.frames}")
            # Checkpoint: last chance before the laser is switched ON.
            _check_cancel()
            self._confirm_laser_on(require_confirmation=confirm)
            print("  > 正在采集样品光谱 (激光开启)...")
            _check_cancel()
            sample_frame = self._capture(should_cancel)
            print("✓ 样品采集完成")

            if self.runtime_mode == "real":
                self._confirm_laser_off(require_confirmation=confirm)
                laser_off_after_sample = True
                print("✓ 激光已关闭")

            print("\n[5/8] 处理光谱数据...")
            background = self._frame_to_spectrum(background_frame) if background_frame is not None else None
            raw = self._frame_to_spectrum(sample_frame)
            print("✓ 光谱数据处理完成")

            print("\n[6/8] 背景扣除...")
            corrected = subtract_background(raw, background) if background is not None else None
            if corrected is not None:
                print("✓ 背景扣除完成")
            else:
                print("⊘ 未执行背景扣除")

            warnings = list(
                dict.fromkeys((background.metadata["warnings"] if background is not None else []) + raw.metadata["warnings"])
            )

            print("\n[7/8] 保存数据文件...")
            self._write_spectrum(run_dir / "raw.csv", raw, "intensity_raw")
            print("  ✓ raw.csv")
            if corrected is not None:
                self._write_spectrum(run_dir / "background.csv", background, "intensity_background")
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
        except BaseException as exc:
            print("\n❌ 采集过程出错!")
            errors = [f"{type(exc).__name__}: {exc}"]
            try:
                if not laser_off_after_sample:
                    self._confirm_laser_off_after_failure(require_confirmation=confirm)
            except Exception as safety_exc:
                exc = safety_exc
                errors.append(f"{type(exc).__name__}: {exc}")
                raise
            finally:
                status = "stopped" if isinstance(exc, (WorkflowCancelled, KeyboardInterrupt)) else "failed"
                try:
                    write_json(run_dir / "metadata.json", {
                        **self._run_metadata(timestamp),
                        "status": status,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "errors": errors,
                    })
                    append_run_log(run_dir / "run.log", f"{status}: {'; '.join(errors)}")
                except OSError as record_exc:
                    print(f"Could not save failure record: {record_exc}")
            raise
        return run_dir

    def _run_metadata(self, timestamp: datetime) -> dict:
        return {
            "timestamp": timestamp.isoformat(),
            "sample_id": self.config.sample.id,
            "operator": self.config.sample.operator,
            "runtime_mode": self.runtime_mode,
            "software_version": __version__,
            "config_snapshot": asdict(self.config),
            "devices_config_snapshot": self.devices_snapshot,
            "excitation": {
                "wavelength_nm": self.config.optics.excitation_wavelength_nm,
                "power_mw": self.config.optics.laser_power_mw,
                "source": "operator_supplied",  # no optical power sensor is connected
            },
            "warnings": [],
            "errors": [],
        }

    def _write_metadata(self, path: Path, *, timestamp: datetime, raw: SpectrumData, sample_frame: CaptureFrame, warnings: list[str]) -> None:
        temperature = None
        try:
            temperature = self.camera.temperature_c()
        except Exception as exc:
            warnings = [*warnings, f"detector temperature unavailable: {exc}"]
        write_json(path, {
            **self._run_metadata(timestamp),
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "x_axis_type": raw.x_axis_type,
            "runtime_mode": self.runtime_mode,
            "stage_position_um": dict(self.stage.ledger.position_um) if self.stage is not None else None,
            "devices": {
                "stage": _read_status(self.stage.identify) if self.stage is not None else None,
                "spectrometer": _read_status(self.spectrometer.status),
                "camera": _read_status(self.camera.status),
            },
            "spectrometer": {
                "grating": self.config.optics.grating,
                "center_wavelength_nm": self.config.optics.center_wavelength_nm,
                "slit_width_um": self.config.optics.slit_width_um,
                "entrance_port": self.config.optics.entrance_port,
                "exit_port": self.config.optics.exit_port,
            },
            "camera": {
                "temperature_c": temperature,
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
        })

    def _confirm_laser_off(self, *, require_confirmation: bool) -> None:
        self.light.confirm_laser_off(require_confirmation=require_confirmation)
        if self.light.laser_state != "off_confirmed":
            raise ConfigError("background capture requires laser_state=off_confirmed")

    def _confirm_laser_on(self, *, require_confirmation: bool) -> None:
        self.light.confirm_laser_on(require_confirmation=require_confirmation)
        if self.light.laser_state != "on_confirmed":
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
        optics = self.config.optics
        self.spectrometer.initialize(entrance_port=optics.entrance_port, exit_port=optics.exit_port)
        self.spectrometer.set_grating(optics.grating)
        self.spectrometer.move_to_wavelength_nm(optics.center_wavelength_nm)
        self.spectrometer.set_slit_width_um(optics.slit_width_um)

    def _write_spectrum(self, path: Path, spectrum: SpectrumData, column: str) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["pixel_index", "wavelength_nm", column, "saturated"])
            for index, (wave, value, saturated) in enumerate(zip(spectrum.x, spectrum.intensity_raw, spectrum.saturated, strict=True)):
                writer.writerow([index, wave, value, str(saturated).lower()])

    def _write_corrected(self, path: Path, spectrum: SpectrumData) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
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
                        str(spectrum.background_saturated[index]).lower(),
                    ]
                )
