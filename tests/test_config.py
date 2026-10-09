from pathlib import Path
import tomllib

import pytest
import yaml

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


def test_load_devices_config_rejects_malformed_soft_limits(tmp_path: Path):
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
  soft_limits_um: {x: [-5000], y: [-5000, 5000], z: [-1000, 1000]}
  state_file: state/stage_position.json
  max_unknown_move_um: 100
spectrometer: {type: zolix, dll_path: C:/SDK/spectrometer_x64.dll, usb_mode: true}
camera: {type: dfield_vs_a4, dll_path: C:/SDK/dfield-vs-a4.dll}
light: {type: manual, manual_light_control: true}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="soft_limits_um"):
        load_devices_config(path)


def test_load_devices_config_rejects_soft_limits_outside_zero_origin(tmp_path):
    data = yaml.safe_load(Path("configs/devices.example.yaml").read_text(encoding="utf-8"))
    data["stage"]["soft_limits_um"]["x"] = [1, 5000]
    path = tmp_path / "devices.yaml"
    path.write_text(yaml.safe_dump(data))

    with pytest.raises(ConfigError, match="origin 0"):
        load_devices_config(path)


def test_load_devices_config_rejects_non_positive_resolution(tmp_path: Path):
    path = tmp_path / "devices.yaml"
    path.write_text(
        """
runtime: {mode: dry_run, log_level: info}
stage:
  type: waynelabs_linear
  port: COM5
  baudrate: 9600
  resolution_um: {x: 0, y: 0.04, z: 0.04}
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

    with pytest.raises(ConfigError, match="resolution_um"):
        load_devices_config(path)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("baudrate", 0, "baudrate"),
        ("default_speed", 10, "default_speed"),
        ("max_unknown_move_um", -1, "max_unknown_move_um"),
    ],
)
def test_load_devices_config_rejects_unsafe_stage_values(tmp_path, field, value, message):
    data = yaml.safe_load(Path("configs/devices.example.yaml").read_text(encoding="utf-8"))
    data["stage"][field] = value
    path = tmp_path / "devices.yaml"
    path.write_text(yaml.safe_dump(data))

    with pytest.raises(ConfigError, match=message):
        load_devices_config(path)


def test_load_devices_config_rejects_unsupported_stage_axis(tmp_path):
    data = yaml.safe_load(Path("configs/devices.example.yaml").read_text(encoding="utf-8"))
    data["stage"]["resolution_um"]["rotary"] = 1
    data["stage"]["soft_limits_um"]["rotary"] = [-1, 1]
    path = tmp_path / "devices.yaml"
    path.write_text(yaml.safe_dump(data))

    with pytest.raises(ConfigError, match="unsupported axes"):
        load_devices_config(path)


@pytest.mark.parametrize(
    ("field_replacement", "message"),
    [
        ("baudrate: .inf", "baudrate"),
        ("default_speed: .inf", "default_speed"),
        ("default_speed: true", "default_speed"),
        ("resolution_um: {x: .inf, y: 0.04, z: 0.04}", "resolution_um"),
        ("soft_limits_um: {x: [.nan, 5000], y: [-5000, 5000], z: [-1000, 1000]}", "soft_limits_um"),
        ("max_unknown_move_um: .nan", "max_unknown_move_um"),
    ],
)
def test_load_devices_config_rejects_non_finite_stage_numbers(tmp_path: Path, field_replacement, message):
    path = tmp_path / "devices.yaml"
    text = """
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
"""
    if field_replacement.startswith("resolution_um"):
        text = text.replace("resolution_um: {x: 0.04, y: 0.04, z: 0.04}", field_replacement)
    elif field_replacement.startswith("soft_limits_um"):
        text = text.replace("soft_limits_um: {x: [-5000, 5000], y: [-5000, 5000], z: [-1000, 1000]}", field_replacement)
    elif field_replacement.startswith("baudrate"):
        text = text.replace("baudrate: 9600", field_replacement)
    elif field_replacement.startswith("default_speed"):
        text = text.replace("default_speed: 8", field_replacement)
    else:
        text = text.replace("max_unknown_move_um: 100", field_replacement)
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
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
""",
        encoding="utf-8",
    )

    config = load_workflow_config(path)

    assert config.devices_config == Path("configs/devices.example.yaml")
    assert config.optics.entrance_port == "side"
    assert config.optics.exit_port == "direct"
    assert config.acquisition.gain == "low"


@pytest.mark.parametrize(
    "sample",
    [
        {"id": None, "operator": "lab"},
        {"id": " sample-001", "operator": "lab"},
        {"id": "sample-001", "operator": "   "},
    ],
)
def test_workflow_rejects_untraceable_sample_metadata(tmp_path, sample):
    data = yaml.safe_load(Path("configs/single_point.example.yaml").read_text(encoding="utf-8"))
    data["sample"] = sample
    path = tmp_path / "single.yaml"
    path.write_text(yaml.safe_dump(data))

    with pytest.raises(ConfigError):
        load_workflow_config(path)


@pytest.mark.parametrize("sample_id", ["CON", "name.", "bad:name", "x" * 129])
def test_workflow_config_rejects_nonportable_sample_id(tmp_path: Path, sample_id):
    data = yaml.safe_load(Path("configs/single_point.example.yaml").read_text(encoding="utf-8"))
    data["sample"]["id"] = sample_id
    path = tmp_path / "single.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ConfigError, match="Windows-safe"):
        load_workflow_config(path)


def test_devices_config_rejects_partial_home_direction_map(tmp_path: Path):
    data = yaml.safe_load(Path("configs/devices.example.yaml").read_text(encoding="utf-8"))
    data["stage"]["home_direction"] = {"x": "negative", "y": "negative"}
    path = tmp_path / "devices.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ConfigError, match="must match configured stage axes"):
        load_devices_config(path)


def test_load_workflow_config_rejects_non_finite_exposure(tmp_path: Path):
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
  exposure_ms: .inf
  gain: low
  read_mode: fvb
  frames: 1
  subtract_background: true
output:
  directory: output/measurements
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="exposure_ms"):
        load_workflow_config(path)


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("grating: .inf", "grating"),
        ("slit_width_um: .inf", "slit_width_um"),
        ("frames: .inf", "frames"),
    ],
)
def test_load_workflow_config_rejects_non_finite_integer_fields(tmp_path: Path, replacement, message):
    path = tmp_path / "single_point.yaml"
    text = """
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
"""
    if replacement.startswith("grating"):
        text = text.replace("grating: 1", replacement)
    elif replacement.startswith("slit_width_um"):
        text = text.replace("slit_width_um: 100", replacement)
    else:
        text = text.replace("frames: 1", replacement)
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_workflow_config(path)


def test_load_devices_config_rejects_fractional_integer_field(tmp_path: Path):
    path = tmp_path / "devices.yaml"
    path.write_text(
        """
runtime: {mode: dry_run, log_level: info}
stage:
  type: waynelabs_linear
  port: COM5
  baudrate: 9600
  resolution_um: {x: 0.04, y: 0.04, z: 0.04}
  default_speed: 8.5
  soft_limits_um: {x: [-5000, 5000], y: [-5000, 5000], z: [-1000, 1000]}
  state_file: state/stage_position.json
  max_unknown_move_um: 100
spectrometer: {type: zolix, dll_path: C:/SDK/spectrometer_x64.dll, usb_mode: true}
camera: {type: dfield_vs_a4, dll_path: C:/SDK/dfield-vs-a4.dll}
light: {type: manual, manual_light_control: true}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="default_speed"):
        load_devices_config(path)


def test_load_devices_config_rejects_malformed_yaml(tmp_path: Path):
    path = tmp_path / "devices.yaml"
    path.write_text("runtime: [\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="configuration YAML is invalid"):
        load_devices_config(path)


def test_load_devices_config_preserves_large_integer_field_without_float_rounding(tmp_path: Path):
    path = tmp_path / "devices.yaml"
    path.write_text(
        """
runtime: {mode: dry_run, log_level: info}
stage:
  type: waynelabs_linear
  port: COM5
  baudrate: 9007199254740993
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

    assert load_devices_config(path).stage.baudrate == 9007199254740993


def test_load_devices_config_rejects_unparseably_huge_integer_field(tmp_path: Path):
    path = tmp_path / "devices.yaml"
    path.write_text(
        f"""
runtime: {{mode: dry_run, log_level: info}}
stage:
  type: waynelabs_linear
  port: COM5
  baudrate: {"1" + "0" * 5000}
  resolution_um: {{x: 0.04, y: 0.04, z: 0.04}}
  default_speed: 8
  soft_limits_um: {{x: [-5000, 5000], y: [-5000, 5000], z: [-1000, 1000]}}
  state_file: state/stage_position.json
  max_unknown_move_um: 100
spectrometer: {{type: zolix, dll_path: C:/SDK/spectrometer_x64.dll, usb_mode: true}}
camera: {{type: dfield_vs_a4, dll_path: C:/SDK/dfield-vs-a4.dll}}
light: {{type: manual, manual_light_control: true}}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="configuration YAML is invalid"):
        load_devices_config(path)


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
output: {directory: output/measurements}
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
