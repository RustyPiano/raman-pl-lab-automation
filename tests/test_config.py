from pathlib import Path
import tomllib

import pytest

from lab_auto.config import load_devices_config, load_workflow_and_devices, load_workflow_config
from lab_auto.errors import ConfigError
from lab_auto.runtime import RuntimeMode, resolve_runtime_mode


def test_load_devices_config_reads_runtime_and_stage(tmp_path: Path):
    path = tmp_path / "devices.yaml"
    path.write_text(
        """
runtime:
  mode: dry_run
  log_level: info
stage:
  type: waynelabs_linear
  port: COM5
  baudrate: 9600
  resolution_um: {x: 0.04, y: 0.04, z: 0.04}
  default_speed: 8
  soft_limits_um: {x: [-5000, 5000], y: [-5000, 5000], z: [-1000, 1000]}
  state_file: state/stage_position.json
  max_unknown_move_um: 100
spectrometer:
  type: zolix
  dll_path: C:/RamanSDK/SDK/x64/spectrometer_x64.dll
camera:
  type: dfield_vs_a4
  dll_path: C:/RamanSDK/DField/x64/dfield-vs-a4.dll
light:
  type: manual
  manual_light_control: true
""",
        encoding="utf-8",
    )

    config = load_devices_config(path)

    assert config.runtime.mode is RuntimeMode.DRY_RUN
    assert config.stage.port == "COM5"
    assert config.stage.resolution_um["x"] == 0.04
    assert config.light.manual_light_control is True


def test_load_devices_config_rejects_string_boolean_for_manual_light_control(tmp_path: Path):
    path = tmp_path / "devices.yaml"
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
light: {type: manual, manual_light_control: "false"}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="manual_light_control"):
        load_devices_config(path)


def test_load_devices_config_rejects_string_boolean_for_usb_mode(tmp_path: Path):
    path = tmp_path / "devices.yaml"
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
spectrometer: {type: zolix, dll_path: C:/SDK/spectrometer_x64.dll, usb_mode: "false"}
camera: {type: dfield_vs_a4, dll_path: C:/SDK/dfield-vs-a4.dll}
light: {type: manual, manual_light_control: true}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="usb_mode"):
        load_devices_config(path)


def test_workflow_config_links_devices_config(tmp_path: Path):
    path = tmp_path / "single_point.yaml"
    path.write_text(
        """
devices_config: configs/devices.example.yaml
sample: {id: sample-001, operator: lab}
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
  directory: output/measurements
  formats: [csv, json]
""",
        encoding="utf-8",
    )

    config = load_workflow_config(path)

    assert config.devices_config == Path("configs/devices.example.yaml")
    assert config.optics.entrance_port == "side"
    assert config.optics.exit_port == "direct"
    assert config.acquisition.gain == "low"


def test_load_workflow_and_devices_allows_devices_override(tmp_path: Path):
    devices = tmp_path / "devices.real.yaml"
    devices.write_text(
        """
runtime: {mode: real, log_level: info}
stage:
  type: waynelabs_linear
  port: COM7
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
    workflow = tmp_path / "single_point.yaml"
    workflow.write_text(
        """
devices_config: configs/devices.example.yaml
sample: {id: sample-001, operator: lab}
optics: {entrance_port: side, exit_port: direct, grating: 1, center_wavelength_nm: 600, slit_width_um: 100}
acquisition: {exposure_ms: 1000, gain: low, read_mode: fvb, frames: 1, subtract_background: true}
output: {directory: output/measurements, formats: [csv, json]}
""",
        encoding="utf-8",
    )

    workflow_config, devices_config = load_workflow_and_devices(workflow, devices_override=devices)

    assert workflow_config.sample.id == "sample-001"
    assert devices_config.runtime.mode is RuntimeMode.REAL
    assert devices_config.stage.port == "COM7"


def test_runtime_cli_override_wins():
    assert resolve_runtime_mode(RuntimeMode.DRY_RUN, cli_real=True) is RuntimeMode.REAL
    assert resolve_runtime_mode(RuntimeMode.REAL, cli_dry_run=True) is RuntimeMode.DRY_RUN
    assert resolve_runtime_mode(RuntimeMode.REAL, cli_simulated=True) is RuntimeMode.SIMULATED


def test_runtime_real_config_requires_explicit_cli_real():
    with pytest.raises(ConfigError, match="requires --real"):
        resolve_runtime_mode(RuntimeMode.REAL)


def test_runtime_override_flags_are_mutually_exclusive():
    with pytest.raises(ConfigError, match="mutually exclusive"):
        resolve_runtime_mode(RuntimeMode.DRY_RUN, cli_real=True, cli_dry_run=True)


def test_pytest_can_import_src_layout_from_clean_checkout():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["tool"]["pytest"]["ini_options"]["pythonpath"] == ["src"]
