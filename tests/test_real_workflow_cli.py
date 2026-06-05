from pathlib import Path

from lab_auto.cli import main


def write_devices_config(path: Path):
    path.write_text(
        """
runtime: {mode: real, log_level: info}
stage:
  type: waynelabs_linear
  port: COM5
  baudrate: 9600
  resolution_um: {x: 0.04, y: 0.04, z: 0.04}
  default_speed: 8
  soft_limits_um: {x: [-5000, 5000], y: [-5000, 5000], z: [-1000, 1000]}
  state_file: state/stage_position.json
  max_unknown_move_um: 100
spectrometer: {type: zolix, dll_path: C:/SDK/spectrometer_x64.dll, usb_mode: true}
camera: {type: dfield_vs_a4, dll_path: C:/SDK/dfield-vs-a4.dll}
light: {type: manual, manual_light_control: true}
""",
        encoding="utf-8",
    )


def write_workflow_config(path: Path, output_dir: Path):
    path.write_text(
        f"""
devices_config: configs/devices.example.yaml
sample: {{id: sample-001, operator: lab}}
optics: {{entrance_port: side, exit_port: direct, grating: 1, center_wavelength_nm: 600, slit_width_um: 100}}
acquisition: {{exposure_ms: 1000, gain: low, read_mode: fvb, frames: 1, subtract_background: true}}
output: {{directory: {output_dir}, formats: [csv, json]}}
""",
        encoding="utf-8",
    )


def test_workflow_single_real_uses_factory_workflow(tmp_path: Path, capsys):
    workflow = tmp_path / "single_point.yaml"
    devices = tmp_path / "devices.real.yaml"
    write_workflow_config(workflow, tmp_path / "out")
    write_devices_config(devices)
    factory = FakeDeviceFactory(tmp_path / "out" / "sample-001")

    exit_code = main(
        ["workflow", "single", "--config", str(workflow), "--devices-config", str(devices), "--real", "--yes"],
        factory=factory,
    )

    assert exit_code == 0
    assert factory.created is True
    assert factory.workflow.calls == [("run_single_point", False), ("close",)]
    assert str(tmp_path / "out" / "sample-001") in capsys.readouterr().out


def test_workflow_single_real_config_without_real_flag_does_not_create_workflow(tmp_path: Path, capsys):
    workflow = tmp_path / "single_point.yaml"
    devices = tmp_path / "devices.real.yaml"
    write_workflow_config(workflow, tmp_path / "out")
    write_devices_config(devices)
    factory = FakeDeviceFactory(tmp_path / "out" / "sample-001")

    exit_code = main(["workflow", "single", "--config", str(workflow), "--devices-config", str(devices), "--yes"], factory=factory)

    assert exit_code == 2
    assert factory.created is False
    assert "requires --real" in capsys.readouterr().out


class FakeDeviceFactory:
    def __init__(self, run_dir: Path):
        self.created = False
        self.workflow = FakeRealWorkflow(run_dir)

    def create_single_point_workflow(self, workflow_config, devices_config):
        self.created = True
        return self.workflow


class FakeRealWorkflow:
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.calls = []

    def run_single_point(self, *, require_confirmation: bool):
        self.calls.append(("run_single_point", require_confirmation))
        return self.run_dir

    def close(self):
        self.calls.append(("close",))
