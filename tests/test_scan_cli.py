from pathlib import Path

from lab_auto.cli import main
from lab_auto.errors import SafetyError


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
  soft_limits_um: {x: [-50000, 50000], y: [-50000, 50000], z: [-1000, 1000]}
  state_file: state/stage_position.json
  max_unknown_move_um: 100
spectrometer: {type: zolix, dll_path: C:/SDK/spectrometer_x64.dll, usb_mode: true}
camera: {type: dfield_vs_a4, dll_path: C:/SDK/dfield-vs-a4.dll}
light: {type: manual, manual_light_control: true}
""",
        encoding="utf-8",
    )


def write_scan_config(path: Path, devices_path: Path, output_dir: Path):
    path.write_text(
        f"""
devices_config: {devices_path}
sample: {{id: tray-001, operator: lab}}
optics: {{entrance_port: side, exit_port: direct, grating: 1, center_wavelength_nm: 600, slit_width_um: 100}}
acquisition: {{exposure_ms: 1000, gain: low, read_mode: fvb, frames: 1, subtract_background: true}}
output: {{directory: {output_dir}}}
tray: {{rows: 1, cols: 1, pitch_x_um: 10000, pitch_y_um: 10000, first_cell_offset_x_um: 0, first_cell_offset_y_um: 0, order: row_major}}
pattern: {{repeats_per_point: 2, burn_metric: relative_l2, burn_threshold: 0.1, surrounding_count: 2, surrounding_distance_um: 20, surrounding_angles_deg: [0, 90]}}
calibration: {{objective: "50x", a11: 0.5, a12: 0.0, a21: 0.0, a22: 0.5, image_center_px: 320, image_center_py: 240}}
min_area: 1
on_out_of_range: skip
""",
        encoding="utf-8",
    )


def test_scan_tray_dry_run_prints_plan(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    scan = tmp_path / "tray_scan.yaml"
    write_devices_config(devices)
    write_scan_config(scan, devices, tmp_path / "out")

    exit_code = main(["scan", "tray", "--config", str(scan), "--dry-run"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "move_wafer:0" in out
    assert "capture_wafer_image:0" in out
    assert "measure:center:rep0" in out
    assert "return_wafer_center:0" in out


def test_scan_tray_real_routes_through_factory(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    scan = tmp_path / "tray_scan.yaml"
    write_devices_config(devices)
    write_scan_config(scan, tmp_path / "unused-devices.yaml", tmp_path / "out")
    factory = FakeScanFactory()

    exit_code = main(
        ["scan", "tray", "--config", str(scan), "--devices-config", str(devices), "--real", "--yes", *_RECOGNITION_ARGS],
        factory=factory,
    )

    assert exit_code == 0
    assert factory.created is True
    assert factory.scan_config.devices_config == devices
    assert factory.workflow.calls == [("run", False), ("close",)]


def test_scan_tray_real_without_real_flag_does_not_create(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    scan = tmp_path / "tray_scan.yaml"
    write_devices_config(devices)
    write_scan_config(scan, devices, tmp_path / "out")
    factory = FakeScanFactory()

    # devices mode is real but --real not passed: refuse, do not create workflow
    exit_code = main(["scan", "tray", "--config", str(scan), "--devices-config", str(devices)], factory=factory)

    assert exit_code == 2
    assert factory.created is False
    assert "requires --real" in capsys.readouterr().out


def test_scan_tray_safety_error_is_recoverable(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    scan = tmp_path / "tray_scan.yaml"
    write_devices_config(devices)
    write_scan_config(scan, devices, tmp_path / "out")
    factory = FakeScanFactory(raise_safety=True)

    exit_code = main(
        ["scan", "tray", "--config", str(scan), "--devices-config", str(devices), "--real", "--yes", *_RECOGNITION_ARGS],
        factory=factory,
    )

    assert exit_code == 2
    assert factory.created is True
    assert "error:" in capsys.readouterr().out


def test_scan_tray_invalid_config_is_recoverable(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    scan = tmp_path / "tray_scan.yaml"
    write_devices_config(devices)
    write_scan_config(scan, devices, tmp_path / "out")
    bad = scan.read_text(encoding="utf-8").replace("on_out_of_range: skip", "on_out_of_range: explode")
    scan.write_text(bad, encoding="utf-8")

    exit_code = main(["scan", "tray", "--config", str(scan), "--dry-run"])
    assert exit_code == 2
    assert "error:" in capsys.readouterr().out


def test_scan_tray_real_without_recognition_handshake_fails_before_hardware(tmp_path: Path, capsys):
    # Without the recognition file handshake a real scan must fail fast
    # (recoverable) without opening devices or moving the stage.
    devices = tmp_path / "devices.yaml"
    scan = tmp_path / "tray_scan.yaml"
    write_devices_config(devices)
    write_scan_config(scan, devices, tmp_path / "out")
    factory = FakeScanFactory()

    exit_code = main(
        ["scan", "tray", "--config", str(scan), "--devices-config", str(devices), "--real", "--yes"],
        factory=factory,
    )

    assert exit_code == 2
    assert factory.created is False
    assert "--recognition-dir" in capsys.readouterr().out


def test_scan_tray_invalid_per_point_config_rejected_early(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    scan = tmp_path / "tray_scan.yaml"
    write_devices_config(devices)
    write_scan_config(scan, devices, tmp_path / "out")
    bad = scan.read_text(encoding="utf-8").replace("read_mode: fvb", "read_mode: image")
    scan.write_text(bad, encoding="utf-8")

    exit_code = main(["scan", "tray", "--config", str(scan), "--dry-run"])

    assert exit_code == 2
    assert "error:" in capsys.readouterr().out


_RECOGNITION_ARGS = ("--recognition-dir", "handoff", "--session-id", "loading-001")


class FakeScanFactory:
    def __init__(self, *, raise_safety: bool = False):
        self.created = False
        self.scan_config = None
        self.workflow = FakeScanWorkflow(raise_safety=raise_safety)

    def create_tray_scan_workflow(self, scan_config, devices_config, *, mask_provider=None):
        self.created = True
        self.scan_config = scan_config
        self.mask_provider = mask_provider
        return self.workflow


class FakeScanWorkflow:
    def __init__(self, *, raise_safety: bool = False):
        self.calls = []
        self.raise_safety = raise_safety

    def run(self, *, require_confirmation: bool):
        self.calls.append(("run", require_confirmation))
        if self.raise_safety:
            raise SafetyError("stage axis unknown")
        return {"wafers": []}

    def close(self):
        self.calls.append(("close",))


def test_scan_cli_connects_session_provider(tmp_path):
    devices, scan = tmp_path / "devices.yaml", tmp_path / "tray.yaml"
    write_devices_config(devices)
    write_scan_config(scan, devices, tmp_path / "output")
    factory = FakeScanFactory()
    assert main([
        "scan", "tray", "--config", str(scan), "--real", "--yes",
        "--recognition-dir", str(tmp_path / "handoff"), "--session-id", "loading-001",
    ], factory=factory) == 0
    assert factory.mask_provider.session_id == "loading-001"
    assert factory.mask_provider.calibration.objective == "50x"
