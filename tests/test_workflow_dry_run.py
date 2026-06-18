from pathlib import Path
import json

from lab_auto.config import AcquisitionConfig, OpticsConfig, OutputConfig, SampleConfig, WorkflowConfig
from lab_auto.devices.light import ManualLight
from lab_auto.devices.simulated import SimulatedCamera, SimulatedSpectrometer
from lab_auto.errors import ConfigError
from lab_auto.workflow.data import CaptureFrame
from lab_auto.workflow.raman import RamanWorkflow


def test_manual_light_records_confirmation_steps():
    light = ManualLight(manual=True)

    assert light.require_off_confirmation() == "confirm_laser_off"
    assert light.require_on_confirmation() == "confirm_laser_on"


def test_simulated_camera_returns_deterministic_fvb_frame():
    camera = SimulatedCamera()

    frame = camera.capture(read_mode="fvb", exposure_ms=1000, gain="low", frames=1)

    assert frame.read_mode == "fvb"
    assert frame.values[:3] == [1000, 1001, 1002]
    assert frame.saturated_count == 0


def test_simulated_spectrometer_pixel_to_wavelength():
    spec = SimulatedSpectrometer()

    waves = spec.pixels_to_waves(turret=0, grating=1, center_wavelength_nm=600.0, width=2048, count=3, bin_x=1)

    assert waves == [599.99, 600.0, 600.01]


def workflow_config(tmp_path: Path):
    return WorkflowConfig(
        devices_config=Path("configs/devices.example.yaml"),
        sample=SampleConfig(id="sample-001", operator="lab"),
        optics=OpticsConfig(
            entrance_port="side",
            exit_port="direct",
            grating=1,
            center_wavelength_nm=600.0,
            slit_width_um=100,
        ),
        acquisition=AcquisitionConfig(
            exposure_ms=1000,
            gain="low",
            read_mode="fvb",
            frames=1,
            subtract_background=True,
        ),
        output=OutputConfig(directory=tmp_path, formats=["csv", "json"]),
    )


def workflow_config_without_background(tmp_path: Path):
    config = workflow_config(tmp_path)
    return WorkflowConfig(
        devices_config=config.devices_config,
        sample=config.sample,
        optics=config.optics,
        acquisition=AcquisitionConfig(
            exposure_ms=config.acquisition.exposure_ms,
            gain=config.acquisition.gain,
            read_mode=config.acquisition.read_mode,
            frames=config.acquisition.frames,
            subtract_background=False,
        ),
        output=config.output,
    )


def test_single_workflow_dry_run_sequence(tmp_path: Path):
    workflow = RamanWorkflow.dry_run(workflow_config(tmp_path))

    actions = workflow.measure_single_point(require_confirmation=False)

    assert actions == [
        "devices_check",
        "set_entrance_port:side",
        "set_exit_port:direct",
        "set_grating:1",
        "move_wavelength_nm:600.0",
        "set_slit_width_um:100",
        "confirm_laser_off",
        "capture_background",
        "confirm_laser_on",
        "capture_sample",
        "subtract_background",
        "save_outputs",
    ]


def test_single_workflow_dry_run_sequence_without_background(tmp_path: Path):
    workflow = RamanWorkflow.dry_run(workflow_config_without_background(tmp_path))

    actions = workflow.measure_single_point(require_confirmation=False)

    assert actions == [
        "devices_check",
        "set_entrance_port:side",
        "set_exit_port:direct",
        "set_grating:1",
        "move_wavelength_nm:600.0",
        "set_slit_width_um:100",
        "confirm_laser_on",
        "capture_sample",
        "save_outputs",
    ]


def test_single_workflow_writes_core_outputs(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))

    run_dir = workflow.run_single_point(require_confirmation=False)

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert run_dir.name.endswith("-sample-001")
    assert metadata["timestamp"]
    assert metadata["camera"]["exposure_ms"] == 1000
    assert metadata["camera"]["gain"] == "low"
    assert metadata["spectrometer"]["center_wavelength_nm"] == 600.0
    assert metadata["devices"]["spectrometer"]["type"] == "simulated"
    assert (run_dir / "metadata.json").exists()
    assert (run_dir / "background.csv").exists()
    assert (run_dir / "raw.csv").exists()
    assert (run_dir / "corrected.csv").exists()
    assert (run_dir / "run.log").exists()
    # simulated workflow has no stage -> position is null, not a stale value
    assert metadata["stage_position_um"] is None


def test_metadata_records_stage_position_when_available(tmp_path: Path):
    from types import SimpleNamespace

    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.stage = SimpleNamespace(ledger=SimpleNamespace(position_um={"x": 12.5, "y": -3.0}))

    run_dir = workflow.run_single_point(require_confirmation=False)

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["stage_position_um"] == {"x": 12.5, "y": -3.0}


def test_single_workflow_uses_distinct_run_directories(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))

    first = workflow.run_single_point(require_confirmation=False)
    second = workflow.run_single_point(require_confirmation=False)

    assert first != second


def test_single_workflow_confirms_laser_states_before_captures(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.spectrometer = NoCalibrationSpectrometer()
    workflow.light = TrackingLight()
    workflow.camera = LightAwareCamera(workflow.light)

    workflow.run_single_point(require_confirmation=False)

    assert workflow.light.calls == ["off", "on"]
    assert workflow.camera.seen_states == ["off_confirmed", "on_confirmed"]


def test_real_manual_light_prompts_even_when_yes_bypasses_other_confirmation(tmp_path: Path, monkeypatch):
    prompts = []
    light = ManualLight(manual=True)
    workflow = RamanWorkflow.real(
        workflow_config(tmp_path),
        stage=None,
        spectrometer=NoCalibrationSpectrometer(),
        camera=LightAwareCamera(light),
        light=light,
    )
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "")

    workflow.run_single_point(require_confirmation=False)

    assert len(prompts) == 3
    assert "OFF" in prompts[0]
    assert "ON" in prompts[1]
    assert "OFF" in prompts[2]


def test_real_single_workflow_confirms_laser_off_after_success(tmp_path: Path):
    events = []
    light = EventTrackingLight(events)
    workflow = RamanWorkflow.real(
        workflow_config(tmp_path),
        stage=None,
        spectrometer=EventSpectrometer(events),
        camera=EventCamera(light, events),
        light=light,
    )

    workflow.run_single_point(require_confirmation=False)

    assert light.calls == ["off", "on", "off"]
    assert workflow.camera.seen_states == ["off_confirmed", "on_confirmed"]
    assert events == ["off", "capture:off_confirmed", "on", "capture:on_confirmed", "off", "calibration", "calibration"]


def test_real_workflow_close_closes_owned_light(tmp_path: Path):
    stage = ClosableDevice()
    spectrometer = ClosableDevice()
    camera = ClosableDevice()
    light = ClosableDevice()
    workflow = RamanWorkflow.real(
        workflow_config(tmp_path),
        stage=stage,
        spectrometer=spectrometer,
        camera=camera,
        light=light,
    )

    workflow.close()

    assert stage.closed is True
    assert spectrometer.closed is True
    assert camera.closed is True
    assert light.closed is True


def test_single_workflow_confirms_laser_off_on_failure(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.spectrometer = NoCalibrationSpectrometer()
    workflow.light = TrackingLight()
    workflow.camera = FailingSampleCamera()

    try:
        workflow.run_single_point(require_confirmation=False)
    except RuntimeError:
        pass

    assert workflow.light.calls == ["off", "on", "off"]


def test_single_workflow_confirms_laser_off_after_processing_failure(tmp_path: Path, monkeypatch):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.spectrometer = NoCalibrationSpectrometer()
    workflow.light = TrackingLight()
    workflow.camera = LightAwareCamera(workflow.light)
    monkeypatch.setattr(workflow, "_write_raw", fail_write)

    try:
        workflow.run_single_point(require_confirmation=False)
    except RuntimeError:
        pass

    assert workflow.light.calls == ["off", "on", "off"]


def test_failed_wavelength_calibration_falls_back_to_pixel_index(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config_without_background(tmp_path))
    workflow.spectrometer = FailingCalibrationSpectrometer()
    workflow.camera = SequentialCamera([[150, 165]])

    run_dir = workflow.run_single_point(require_confirmation=False)

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    raw_lines = (run_dir / "raw.csv").read_text(encoding="utf-8").splitlines()
    assert metadata["x_axis_type"] == "pixel_index"
    assert "wavelength calibration failed; using pixel_index" in metadata["warnings"]
    assert raw_lines[0] == "pixel_index,intensity_raw,saturated"


def test_mixed_wavelength_calibration_fallback_still_subtracts_background(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.spectrometer = IntermittentCalibrationSpectrometer()
    workflow.camera = SequentialCamera([[100, 110], [150, 165]])

    run_dir = workflow.run_single_point(require_confirmation=False)

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    corrected_lines = (run_dir / "corrected.csv").read_text(encoding="utf-8").splitlines()
    assert metadata["x_axis_type"] == "pixel_index"
    assert "wavelength calibration failed; using pixel_index" in metadata["warnings"]
    assert corrected_lines[0] == "pixel_index,intensity_raw,intensity_background,intensity_corrected,saturated_raw,saturated_background"
    assert corrected_lines[1] == "0,150.0,100.0,50.0,false,false"


def test_real_manual_light_prompts_laser_off_on_failure_even_with_yes(tmp_path: Path, monkeypatch):
    prompts = []
    light = ManualLight(manual=True)
    workflow = RamanWorkflow.real(
        workflow_config(tmp_path),
        stage=None,
        spectrometer=NoCalibrationSpectrometer(),
        camera=FailingSampleCamera(),
        light=light,
    )
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "")

    try:
        workflow.run_single_point(require_confirmation=False)
    except RuntimeError:
        pass

    assert len(prompts) == 3
    assert "OFF" in prompts[-1]


def test_workflow_uses_detector_width_for_binned_wavelength_calibration(tmp_path: Path):
    spec = RecordingSpectrometer()
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.spectrometer = spec
    workflow.camera = BinnedCamera()

    workflow.run_single_point(require_confirmation=False)

    assert spec.calls == [(4, 2), (4, 2)]


def test_single_workflow_can_skip_background_subtraction(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config_without_background(tmp_path))
    workflow.spectrometer = NoCalibrationSpectrometer()
    workflow.camera = SequentialCamera([[150, 165]])

    run_dir = workflow.run_single_point(require_confirmation=False)

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["background_subtraction"]["enabled"] is False
    assert (run_dir / "raw.csv").exists()
    assert not (run_dir / "background.csv").exists()
    assert not (run_dir / "corrected.csv").exists()


def test_single_workflow_rejects_image_read_mode(tmp_path: Path):
    config = workflow_config(tmp_path)
    workflow = RamanWorkflow.simulated(
        WorkflowConfig(
            devices_config=config.devices_config,
            sample=config.sample,
            optics=config.optics,
            acquisition=AcquisitionConfig(
                exposure_ms=config.acquisition.exposure_ms,
                gain=config.acquisition.gain,
                read_mode="image",
                frames=config.acquisition.frames,
                subtract_background=config.acquisition.subtract_background,
            ),
            output=config.output,
        )
    )

    try:
        workflow.run_single_point(require_confirmation=False)
    except ConfigError as exc:
        assert "single-point workflow requires read_mode=fvb" in str(exc)
    else:
        raise AssertionError("expected ConfigError")


def test_single_workflow_subtracts_captured_background_values(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.spectrometer = NoCalibrationSpectrometer()
    workflow.camera = SequentialCamera([[100, 110], [150, 165]])

    run_dir = workflow.run_single_point(require_confirmation=False)

    corrected_lines = (run_dir / "corrected.csv").read_text(encoding="utf-8").splitlines()
    assert corrected_lines[0] == "pixel_index,intensity_raw,intensity_background,intensity_corrected,saturated_raw,saturated_background"
    assert corrected_lines[1] == "0,150.0,100.0,50.0,false,false"
    assert corrected_lines[2] == "1,165.0,110.0,55.0,false,false"


def test_single_workflow_records_axis_fallback_and_saturation_warnings(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.spectrometer = NoCalibrationSpectrometer()
    workflow.camera = SaturatedCamera()

    run_dir = workflow.run_single_point(require_confirmation=False)

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    raw_lines = (run_dir / "raw.csv").read_text(encoding="utf-8").splitlines()
    assert metadata["x_axis_type"] == "pixel_index"
    assert "wavelength calibration unavailable; using pixel_index" in metadata["warnings"]
    assert "saturated pixels detected" in metadata["warnings"]
    assert metadata["camera"]["saturated_count"] == 1
    assert metadata["camera"]["saturation_threshold"] == 65535
    assert metadata["camera"]["raw_frames_count"] == 1
    assert raw_lines[0] == "pixel_index,intensity_raw,saturated"
    assert raw_lines[1].endswith(",true")


class NoCalibrationSpectrometer:
    def __init__(self):
        self.calls = []

    def pixels_to_waves(self, **kwargs):
        self.calls.append(len(self.calls))
        return []


class EventSpectrometer(NoCalibrationSpectrometer):
    def __init__(self, events: list[str]):
        super().__init__()
        self.events = events

    def pixels_to_waves(self, **kwargs):
        self.events.append("calibration")
        return super().pixels_to_waves(**kwargs)


class FailingCalibrationSpectrometer:
    def pixels_to_waves(self, **kwargs):
        raise RuntimeError("calibration failed")


class IntermittentCalibrationSpectrometer:
    def __init__(self):
        self.calls = 0

    def pixels_to_waves(self, *, center_wavelength_nm: float, count: int, **kwargs):
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("calibration failed")
        return [center_wavelength_nm + index for index in range(count)]


def fail_write(*args, **kwargs):
    raise RuntimeError("write failed")


class SequentialCamera:
    def __init__(self, frames: list[list[int]]):
        self.frames = list(frames)

    def capture(self, *, read_mode: str, exposure_ms: float, gain: str, frames: int) -> CaptureFrame:
        values = self.frames.pop(0)
        return CaptureFrame(
            read_mode=read_mode,
            width=len(values),
            height=1,
            bin_x=1,
            bin_y=1,
            roi=None,
            exposure_ms=exposure_ms,
            gain=gain,
            values=values,
            saturated_count=0,
            saturated=[False for _ in values],
            metadata={"raw_frames_count": frames, "saturation_threshold": 65535},
            raw_frames_count=frames,
            saturation_threshold=65535,
        )


class SaturatedCamera:
    def capture(self, *, read_mode: str, exposure_ms: float, gain: str, frames: int) -> CaptureFrame:
        return CaptureFrame(
            read_mode=read_mode,
            width=2,
            height=1,
            bin_x=1,
            bin_y=1,
            roi=None,
            exposure_ms=exposure_ms,
            gain=gain,
            values=[65535, 100],
            saturated_count=1,
            saturated=[True, False],
            metadata={"raw_frames_count": frames, "saturation_threshold": 65535},
            raw_frames_count=frames,
            saturation_threshold=65535,
        )


class TrackingLight:
    def __init__(self):
        self.calls = []
        self.laser_state = "unknown"

    def require_off_confirmation(self):
        return "confirm_laser_off"

    def require_on_confirmation(self):
        return "confirm_laser_on"

    def confirm_laser_off(self, *, require_confirmation: bool):
        self.calls.append("off")
        self.laser_state = "off_confirmed"

    def confirm_laser_on(self, *, require_confirmation: bool):
        self.calls.append("on")
        self.laser_state = "on_confirmed"


class EventTrackingLight(TrackingLight):
    def __init__(self, events: list[str]):
        super().__init__()
        self.events = events

    def confirm_laser_off(self, *, require_confirmation: bool):
        super().confirm_laser_off(require_confirmation=require_confirmation)
        self.events.append("off")

    def confirm_laser_on(self, *, require_confirmation: bool):
        super().confirm_laser_on(require_confirmation=require_confirmation)
        self.events.append("on")


class LightAwareCamera:
    def __init__(self, light: TrackingLight):
        self.light = light
        self.seen_states = []

    def capture(self, *, read_mode: str, exposure_ms: float, gain: str, frames: int) -> CaptureFrame:
        self.seen_states.append(self.light.laser_state)
        return CaptureFrame(
            read_mode=read_mode,
            width=2,
            height=1,
            bin_x=1,
            bin_y=1,
            roi=None,
            exposure_ms=exposure_ms,
            gain=gain,
            values=[100, 110],
            saturated_count=0,
            saturated=[False, False],
            metadata={"raw_frames_count": frames, "saturation_threshold": 65535},
            raw_frames_count=frames,
            saturation_threshold=65535,
        )


class EventCamera(LightAwareCamera):
    def __init__(self, light: TrackingLight, events: list[str]):
        super().__init__(light)
        self.events = events

    def capture(self, *, read_mode: str, exposure_ms: float, gain: str, frames: int) -> CaptureFrame:
        self.events.append(f"capture:{self.light.laser_state}")
        return super().capture(read_mode=read_mode, exposure_ms=exposure_ms, gain=gain, frames=frames)


class FailingSampleCamera:
    def __init__(self):
        self.calls = 0

    def capture(self, *, read_mode: str, exposure_ms: float, gain: str, frames: int) -> CaptureFrame:
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("sample capture failed")
        return CaptureFrame(
            read_mode=read_mode,
            width=2,
            height=1,
            bin_x=1,
            bin_y=1,
            roi=None,
            exposure_ms=exposure_ms,
            gain=gain,
            values=[100, 110],
            saturated_count=0,
            saturated=[False, False],
            metadata={"raw_frames_count": frames, "saturation_threshold": 65535},
            raw_frames_count=frames,
            saturation_threshold=65535,
        )


class RecordingSpectrometer:
    def __init__(self):
        self.calls = []

    def pixels_to_waves(self, *, turret: int, grating: int, center_wavelength_nm: float, width: int, count: int, bin_x: int) -> list[float]:
        self.calls.append((width, bin_x))
        return [center_wavelength_nm + index for index in range(count)]


class BinnedCamera:
    def capture(self, *, read_mode: str, exposure_ms: float, gain: str, frames: int) -> CaptureFrame:
        return CaptureFrame(
            read_mode=read_mode,
            width=2,
            height=1,
            bin_x=2,
            bin_y=1,
            roi=None,
            exposure_ms=exposure_ms,
            gain=gain,
            values=[100, 110],
            saturated_count=0,
            saturated=[False, False],
            metadata={"detector_width": 4, "detector_height": 1, "raw_frames_count": frames, "saturation_threshold": 65535},
            raw_frames_count=frames,
            saturation_threshold=65535,
        )


class ClosableDevice:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True
