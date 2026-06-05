from pathlib import Path

import pytest

from lab_auto.cli import main


def write_workflow_config(path: Path, output_dir: Path):
    path.write_text(
        f"""
devices_config: configs/devices.example.yaml
sample: {{id: sample-001, operator: lab}}
optics:
  entrance_port: side
  exit_port: direct
  grating: 1
  center_wavelength_nm: 600
  slit_width_um: 100
acquisition:
  exposure_ms: 1000
  gain: low
  read_mode: fvb
  frames: 1
  subtract_background: true
output:
  directory: {output_dir}
  formats: [csv, json]
""",
        encoding="utf-8",
    )


def write_devices_config(path: Path):
    path.write_text(
        """
runtime: {mode: dry_run, log_level: info}
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


def test_workflow_single_dry_run_prints_sequence(tmp_path: Path, capsys):
    config = tmp_path / "single_point.yaml"
    write_workflow_config(config, tmp_path / "out")

    exit_code = main(["workflow", "single", "--config", str(config), "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "confirm_laser_off" in captured.out
    assert "capture_sample" in captured.out


def test_workflow_single_devices_config_override_is_loaded(tmp_path: Path, capsys):
    workflow = tmp_path / "single_point.yaml"
    devices = tmp_path / "devices.real.yaml"
    write_workflow_config(workflow, tmp_path / "out")
    write_devices_config(devices)

    exit_code = main(["workflow", "single", "--config", str(workflow), "--devices-config", str(devices), "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"devices_config:{devices}" in captured.out


def test_workflow_single_dry_run_validates_adapter_constrained_config(tmp_path: Path, capsys):
    config = tmp_path / "single_point.yaml"
    write_workflow_config(config, tmp_path / "out")
    config.write_text(
        config.read_text(encoding="utf-8")
        .replace("entrance_port: side", "entrance_port: bogus")
        .replace("gain: low", "gain: bogus")
        .replace("read_mode: fvb", "read_mode: bogus")
        .replace("exposure_ms: 1000", "exposure_ms: -1")
        .replace("frames: 1", "frames: 0"),
        encoding="utf-8",
    )

    exit_code = main(["workflow", "single", "--config", str(config), "--dry-run"])

    assert exit_code == 2
    assert "unsupported Zolix port" in capsys.readouterr().out


def test_workflow_single_dry_run_rejects_image_read_mode(tmp_path: Path, capsys):
    config = tmp_path / "single_point.yaml"
    write_workflow_config(config, tmp_path / "out")
    config.write_text(config.read_text(encoding="utf-8").replace("read_mode: fvb", "read_mode: image"), encoding="utf-8")

    exit_code = main(["workflow", "single", "--config", str(config), "--dry-run"])

    assert exit_code == 2
    assert "single-point workflow requires read_mode=fvb" in capsys.readouterr().out


def test_workflow_single_dry_run_rejects_invalid_optics_values(tmp_path: Path, capsys):
    config = tmp_path / "single_point.yaml"
    write_workflow_config(config, tmp_path / "out")
    config.write_text(
        config.read_text(encoding="utf-8").replace("center_wavelength_nm: 600", "center_wavelength_nm: -1").replace("slit_width_um: 100", "slit_width_um: -5"),
        encoding="utf-8",
    )

    exit_code = main(["workflow", "single", "--config", str(config), "--dry-run"])

    assert exit_code == 2
    assert "wavelength" in capsys.readouterr().out


def test_devices_real_requires_config(capsys):
    exit_code = main(["devices", "doctor", "--real"])

    assert exit_code == 2
    assert "--config" in capsys.readouterr().out


def test_phase1_hardware_dry_run_commands_exist(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)

    commands = [
        ["devices", "doctor", "--config", str(devices), "--dry-run"],
        ["stage", "identify", "--config", str(devices), "--dry-run"],
        ["stage", "move", "--config", str(devices), "--axis", "x", "--um", "10", "--speed", "8", "--dry-run"],
        ["stage", "home", "--config", str(devices), "--axis", "x", "--direction", "negative", "--speed", "8", "--yes", "--dry-run"],
        ["spec", "status", "--config", str(devices), "--dry-run"],
        ["spec", "init", "--config", str(devices), "--entrance", "side", "--exit", "direct", "--dry-run"],
        ["spec", "set", "--config", str(devices), "--grating", "1", "--wavelength-nm", "600", "--slit-um", "100", "--dry-run"],
        ["camera", "status", "--config", str(devices), "--dry-run"],
        ["camera", "capture", "--config", str(devices), "--mode", "fvb", "--exposure-ms", "1000", "--gain", "low", "--out", str(tmp_path / "fvb.csv"), "--dry-run"],
    ]

    for command in commands:
        assert main(command) == 0

    captured = capsys.readouterr()
    assert "devices_doctor" in captured.out
    assert "stage_move:x:10.0" in captured.out
    assert "spec_set:grating=1:wavelength_nm=600.0:slit_um=100" in captured.out
    assert "camera_capture:mode=fvb:out=" in captured.out


def test_spec_init_dry_run_validates_ports(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)

    exit_code = main(["spec", "init", "--config", str(devices), "--entrance", "bogus", "--exit", "direct", "--dry-run"])

    assert exit_code == 2
    assert "unsupported Zolix port" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("move_args", "message"),
    [
        (["--axis", "q", "--um", "10", "--speed", "8"], "unsupported stage axis"),
        (["--axis", "x", "--um", "10", "--speed", "12"], "speed"),
        (["--axis", "x", "--um", "1000", "--speed", "8"], "unknown position"),
    ],
)
def test_stage_move_dry_run_validates_adapter_constraints(tmp_path: Path, capsys, move_args, message):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)

    exit_code = main(["stage", "move", "--config", str(devices), "--dry-run", *move_args])

    assert exit_code == 2
    assert message in capsys.readouterr().out


def test_camera_capture_dry_run_validates_mode_and_gain(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)

    exit_code = main(
        [
            "camera",
            "capture",
            "--config",
            str(devices),
            "--mode",
            "bad",
            "--exposure-ms",
            "1000",
            "--gain",
            "bad",
            "--out",
            str(tmp_path / "capture.csv"),
            "--dry-run",
        ]
    )

    assert exit_code == 2
    assert "unsupported DField" in capsys.readouterr().out


@pytest.mark.parametrize("bin_args", [["--bin-x", "0"], ["--bin-x", "65"], ["--bin-y", "0"], ["--bin-y", "130"]])
def test_camera_capture_dry_run_validates_bin_bounds(tmp_path: Path, capsys, bin_args):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)

    exit_code = main(
        [
            "camera",
            "capture",
            "--config",
            str(devices),
            "--mode",
            "fvb",
            "--exposure-ms",
            "1000",
            "--gain",
            "low",
            "--out",
            str(tmp_path / "capture.csv"),
            "--dry-run",
            *bin_args,
        ]
    )

    assert exit_code == 2
    assert "bin" in capsys.readouterr().out


def test_camera_capture_dry_run_validates_roi_bounds(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)

    exit_code = main(
        [
            "camera",
            "capture",
            "--config",
            str(devices),
            "--mode",
            "image",
            "--exposure-ms",
            "1000",
            "--gain",
            "low",
            "--out",
            str(tmp_path / "capture.csv"),
            "--roi",
            "2,1,0,7",
            "--dry-run",
        ]
    )

    assert exit_code == 2
    assert "ROI" in capsys.readouterr().out


def test_camera_capture_dry_run_rejects_fvb_roi(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)

    exit_code = main(
        [
            "camera",
            "capture",
            "--config",
            str(devices),
            "--mode",
            "fvb",
            "--exposure-ms",
            "1000",
            "--gain",
            "low",
            "--out",
            str(tmp_path / "capture.csv"),
            "--roi",
            "0,1,0,0",
            "--dry-run",
        ]
    )

    assert exit_code == 2
    assert "ROI" in capsys.readouterr().out


def test_camera_capture_simulated_validates_detector_roi_bounds(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)

    exit_code = main(
        [
            "camera",
            "capture",
            "--config",
            str(devices),
            "--mode",
            "image",
            "--exposure-ms",
            "1000",
            "--gain",
            "low",
            "--out",
            str(tmp_path / "capture.csv"),
            "--roi",
            "99,100,0,1",
            "--simulated",
        ]
    )

    assert exit_code == 2
    assert "ROI" in capsys.readouterr().out


def test_camera_capture_simulated_validates_positive_binned_roi_size(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)

    exit_code = main(
        [
            "camera",
            "capture",
            "--config",
            str(devices),
            "--mode",
            "image",
            "--exposure-ms",
            "1000",
            "--gain",
            "low",
            "--out",
            str(tmp_path / "capture.csv"),
            "--roi",
            "0,0,0,0",
            "--bin-x",
            "64",
            "--simulated",
        ]
    )

    assert exit_code == 2
    assert "size" in capsys.readouterr().out


def test_camera_capture_malformed_roi_returns_config_error(tmp_path: Path, capsys):
    devices = tmp_path / "devices.yaml"
    write_devices_config(devices)

    exit_code = main(
        [
            "camera",
            "capture",
            "--config",
            str(devices),
            "--mode",
            "image",
            "--exposure-ms",
            "1000",
            "--gain",
            "low",
            "--out",
            str(tmp_path / "capture.csv"),
            "--roi",
            "a,b,c,d",
            "--dry-run",
        ]
    )

    assert exit_code == 2
    assert "--roi" in capsys.readouterr().out


def test_camera_capture_simulated_writes_deterministic_csv(tmp_path: Path):
    devices = tmp_path / "devices.yaml"
    out = tmp_path / "capture.csv"
    write_devices_config(devices)

    exit_code = main(
        [
            "camera",
            "capture",
            "--config",
            str(devices),
            "--mode",
            "fvb",
            "--exposure-ms",
            "1000",
            "--gain",
            "low",
            "--out",
            str(out),
            "--simulated",
        ]
    )

    assert exit_code == 0
    assert out.read_text(encoding="utf-8").splitlines()[:2] == [
        "pixel_index,intensity_raw,saturated",
        "0,1000,false",
    ]
