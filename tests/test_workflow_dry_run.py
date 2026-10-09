from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from lab_auto.config import AcquisitionConfig, OpticsConfig, OutputConfig, SampleConfig, WorkflowConfig
from lab_auto.devices.light import ManualLight
from lab_auto.devices.simulated import SimulatedCamera, SimulatedSpectrometer
from lab_auto.errors import ConfigError, DeviceError, WorkflowCancelled
from lab_auto.workflow.data import CaptureFrame
from lab_auto.workflow.raman import RamanWorkflow


def test_manual_light_records_confirmation_steps():
    light = ManualLight()

    assert light.require_off_confirmation() == "confirm_laser_off"
    assert light.require_on_confirmation() == "confirm_laser_on"


def test_simulated_camera_returns_deterministic_fvb_frame():
    camera = SimulatedCamera()

    frame = camera.capture(read_mode="fvb", exposure_ms=1000, gain="low", frames=1)

    assert frame.read_mode == "fvb"
    assert frame.values[:3] == [1000, 1001, 1002]
    assert not any(frame.saturated)


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
        output=OutputConfig(directory=tmp_path),
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
    assert metadata["x_axis_type"] == "wavelength_nm"
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


def test_simulated_sample_has_peak_only_with_laser_on(tmp_path: Path):
    run_dir = RamanWorkflow.simulated(workflow_config(tmp_path)).run_single_point(require_confirmation=False)

    corrected = [float(line.split(",")[4]) for line in (run_dir / "corrected.csv").read_text(encoding="utf-8").splitlines()[1:]]
    assert corrected[0] == 0.0
    assert max(corrected) > 1000


def test_metadata_records_stage_position_and_identify_error(tmp_path: Path):
    def identify():
        raise DeviceError("identify response split")

    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.stage = SimpleNamespace(ledger=SimpleNamespace(position_um={"x": 12.5, "y": -3.0}), identify=identify)

    run_dir = workflow.run_single_point(require_confirmation=False)

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "completed"
    assert metadata["stage_position_um"] == {"x": 12.5, "y": -3.0}
    assert metadata["devices"]["stage"] == {"status_error": "identify response split"}


def test_single_workflow_uses_distinct_run_directories(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))

    first = workflow.run_single_point(require_confirmation=False)
    second = workflow.run_single_point(require_confirmation=False)

    assert first != second


def test_single_workflow_confirms_laser_states_before_captures(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.light = TrackingLight()
    workflow.camera = LightAwareCamera(workflow.light)

    workflow.run_single_point(require_confirmation=False)

    assert workflow.light.calls == ["off", "on"]
    assert workflow.camera.seen_states == ["off_confirmed", "on_confirmed"]


def test_real_manual_light_prompts_even_when_yes_bypasses_other_confirmation(tmp_path: Path, monkeypatch):
    prompts = []
    light = ManualLight()
    workflow = RamanWorkflow.real(
        workflow_config(tmp_path),
        stage=None,
        spectrometer=SimulatedSpectrometer(),
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


def test_run_single_point_cancels_before_any_hardware(tmp_path: Path):
    # should_cancel True from the start: raise at the first checkpoint (after config
    # validation, before the run dir is created) — nothing to clean up.
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))

    with pytest.raises(WorkflowCancelled):
        workflow.run_single_point(require_confirmation=False, should_cancel=lambda: True)

    assert list(tmp_path.iterdir()) == []  # no run directory written


def test_run_single_point_cancel_before_laser_on_forces_laser_off(tmp_path: Path):
    # Cancelling at the 'before laser on' checkpoint must route through the failure
    # path that forces a laser-off confirmation, without ever turning the laser on.
    workflow = RamanWorkflow.simulated(workflow_config_without_background(tmp_path))
    workflow.light = TrackingLight()
    workflow.camera = LightAwareCamera(workflow.light)

    calls = {"n": 0}

    def should_cancel():
        # checkpoints (no background): 1=after validate, 2=before configure,
        # 3=before laser on -> trigger here.
        calls["n"] += 1
        return calls["n"] >= 3

    with pytest.raises(WorkflowCancelled):
        workflow.run_single_point(require_confirmation=False, should_cancel=should_cancel)

    # laser never turned on; the failure path confirmed it OFF
    assert workflow.light.calls == ["off"]


def test_single_workflow_confirms_laser_off_on_failure(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.light = TrackingLight()
    workflow.camera = FailingSampleCamera()

    with pytest.raises(RuntimeError):
        workflow.run_single_point(require_confirmation=False)

    assert workflow.light.calls == ["off", "on", "off"]


def test_single_workflow_confirms_laser_off_after_processing_failure(tmp_path: Path, monkeypatch):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.light = TrackingLight()
    workflow.camera = LightAwareCamera(workflow.light)
    monkeypatch.setattr(workflow, "_write_spectrum", fail_write)

    with pytest.raises(RuntimeError):
        workflow.run_single_point(require_confirmation=False)

    assert workflow.light.calls == ["off", "on", "off"]


def test_failed_wavelength_calibration_fails_the_run(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config_without_background(tmp_path))
    workflow.spectrometer = FailingCalibrationSpectrometer()
    workflow.light = TrackingLight()
    workflow.camera = SequentialCamera([[150, 165]])

    with pytest.raises(RuntimeError, match="calibration failed"):
        workflow.run_single_point(require_confirmation=False)

    run_dir = next(tmp_path.iterdir())
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert not (run_dir / "raw.csv").exists()
    assert workflow.light.calls == ["on", "off"]


def test_wavelength_calibration_length_mismatch_fails_the_run(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config_without_background(tmp_path))
    workflow.spectrometer = ShortCalibrationSpectrometer()
    workflow.camera = SequentialCamera([[150, 165]])

    with pytest.raises(DeviceError, match="wavelength calibration returned 1 values for 2 pixels"):
        workflow.run_single_point(require_confirmation=False)


def test_real_manual_light_prompts_laser_off_on_failure_even_with_yes(tmp_path: Path, monkeypatch):
    prompts = []
    light = ManualLight()
    workflow = RamanWorkflow.real(
        workflow_config(tmp_path),
        stage=None,
        spectrometer=SimulatedSpectrometer(),
        camera=FailingSampleCamera(),
        light=light,
    )
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "")

    with pytest.raises(RuntimeError):
        workflow.run_single_point(require_confirmation=False)

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

    with pytest.raises(ConfigError, match="single-point workflow requires read_mode=fvb"):
        workflow.run_single_point(require_confirmation=False)


def test_single_workflow_subtracts_captured_background_values(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.camera = SequentialCamera([[100, 110], [150, 165]])

    run_dir = workflow.run_single_point(require_confirmation=False)

    corrected_lines = (run_dir / "corrected.csv").read_text(encoding="utf-8").splitlines()
    assert corrected_lines[0] == "pixel_index,wavelength_nm,intensity_raw,intensity_background,intensity_corrected,saturated_raw,saturated_background"
    assert corrected_lines[1] == "0,599.995,150.0,100.0,50.0,false,false"
    assert corrected_lines[2] == "1,600.005,165.0,110.0,55.0,false,false"


def test_single_workflow_records_saturation_warnings(tmp_path: Path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))
    workflow.camera = SaturatedCamera()

    run_dir = workflow.run_single_point(require_confirmation=False)

    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    raw_lines = (run_dir / "raw.csv").read_text(encoding="utf-8").splitlines()
    assert metadata["x_axis_type"] == "wavelength_nm"
    assert "saturated pixels detected" in metadata["warnings"]
    assert metadata["camera"]["saturated_count"] == 1
    assert metadata["camera"]["saturation_threshold"] == 65535
    assert metadata["camera"]["raw_frames_count"] == 1
    assert raw_lines[0] == "pixel_index,wavelength_nm,intensity_raw,saturated"
    assert raw_lines[1].endswith(",true")


class EventSpectrometer(SimulatedSpectrometer):
    def __init__(self, events: list[str]):
        super().__init__()
        self.events = events

    def pixels_to_waves(self, **kwargs):
        self.events.append("calibration")
        return super().pixels_to_waves(**kwargs)


class FailingCalibrationSpectrometer(SimulatedSpectrometer):
    def pixels_to_waves(self, **kwargs):
        raise RuntimeError("calibration failed")


class ShortCalibrationSpectrometer(SimulatedSpectrometer):
    def pixels_to_waves(self, **kwargs):
        return [600.0]


class RecordingSpectrometer(SimulatedSpectrometer):
    def __init__(self):
        super().__init__()
        self.calls = []

    def pixels_to_waves(self, *, width: int, bin_x: int, **kwargs) -> list[float]:
        self.calls.append((width, bin_x))
        return super().pixels_to_waves(width=width, bin_x=bin_x, **kwargs)


def fail_write(*args, **kwargs):
    raise RuntimeError("write failed")


def _frame(values, *, saturated=None, bin_x=1, metadata=None, read_mode="fvb", exposure_ms=1000, gain="low", frames=1):
    return CaptureFrame(
        read_mode=read_mode,
        width=len(values),
        height=1,
        bin_x=bin_x,
        bin_y=1,
        roi=None,
        exposure_ms=exposure_ms,
        gain=gain,
        values=values,
        saturated=saturated or [False for _ in values],
        metadata={"raw_frames_count": frames, "saturation_threshold": 65535, **(metadata or {})},
        raw_frames_count=frames,
        saturation_threshold=65535,
    )


class FakeCamera:
    def status(self):
        return {"type": "fake"}

    def temperature_c(self):
        return 20.0


class SequentialCamera(FakeCamera):
    def __init__(self, frames: list[list[int]]):
        self.frames = list(frames)

    def capture(self, **kwargs) -> CaptureFrame:
        return _frame(self.frames.pop(0))


class SaturatedCamera(FakeCamera):
    def capture(self, **kwargs) -> CaptureFrame:
        return _frame([65535, 100], saturated=[True, False])


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


class LightAwareCamera(FakeCamera):
    def __init__(self, light):
        self.light = light
        self.seen_states = []

    def capture(self, **kwargs) -> CaptureFrame:
        self.seen_states.append(self.light.laser_state)
        return _frame([100, 110])


class EventCamera(LightAwareCamera):
    def __init__(self, light, events: list[str]):
        super().__init__(light)
        self.events = events

    def capture(self, **kwargs) -> CaptureFrame:
        self.events.append(f"capture:{self.light.laser_state}")
        return super().capture(**kwargs)


class FailingSampleCamera(FakeCamera):
    def __init__(self):
        self.calls = 0

    def capture(self, **kwargs) -> CaptureFrame:
        self.calls += 1
        if self.calls == 2:
            raise RuntimeError("sample capture failed")
        return _frame([100, 110])


class BinnedCamera(FakeCamera):
    def capture(self, **kwargs) -> CaptureFrame:
        return _frame([100, 110], bin_x=2, metadata={"detector_width": 4, "detector_height": 1})


class ClosableDevice:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True
