import copy

import pytest
import yaml

from lab_auto.config import load_devices_config
from lab_auto.errors import ConfigError


BASE = {
    "runtime": {"mode": "dry_run", "log_level": "info"},
    "stage": {
        "type": "waynelabs_linear",
        "port": "COM5",
        "baudrate": 9600,
        "resolution_um": {"x": 0.04, "y": 0.04, "z": 0.04},
        "default_speed": 8,
        "soft_limits_um": {"x": [-5000, 5000], "y": [-5000, 5000], "z": [-1000, 1000]},
        "state_file": "state/stage_position.json",
        "max_unknown_move_um": 100,
    },
    "spectrometer": {"type": "zolix", "dll_path": "C:/x.dll", "usb_mode": True},
    "camera": {"type": "dfield_vs_a4", "dll_path": "C:/y.dll"},
    "light": {"type": "manual", "manual_light_control": True},
}

PWM_LIGHT = {
    "type": "pwm_modbus",
    "manual_light_control": False,
    "port": "COM7",
    "station_id": 1,
    "baudrate": 9600,
    "max_output_voltage_v": 5.0,
    "required_output_voltage_v": 5.0,
    "channels": {
        "led": {"channel": 1, "frequency_hz": 1000, "duty_percent": 5.0, "default_off_required": True},
        "laser": {"channel": 2, "frequency_hz": 1000, "duty_percent": 5.0, "default_off_required": True},
    },
}


def _write(tmp_path, light):
    data = copy.deepcopy(BASE)
    data["light"] = copy.deepcopy(light)
    path = tmp_path / "devices.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_manual_light_still_loads(tmp_path):
    cfg = load_devices_config(_write(tmp_path, BASE["light"]))
    assert cfg.light.type == "manual"
    assert cfg.light.manual_light_control is True
    assert cfg.light.channels is None


def test_pwm_light_loads(tmp_path):
    cfg = load_devices_config(_write(tmp_path, PWM_LIGHT))
    light = cfg.light
    assert light.type == "pwm_modbus"
    assert light.manual_light_control is False
    assert light.port == "COM7"
    assert light.station_id == 1
    assert light.max_output_voltage_v == 5.0
    assert light.channels["laser"].channel == 2
    assert light.channels["laser"].frequency_hz == 1000
    assert light.channels["laser"].duty_percent == 5.0
    assert light.channels["led"].default_off_required is True


def _pwm_with(**overrides):
    light = copy.deepcopy(PWM_LIGHT)
    light.update(overrides)
    return light


def test_unknown_type_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, {"type": "laser_blaster", "manual_light_control": False}))


def test_station_zero_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, _pwm_with(station_id=0)))


def test_voltage_over_cap_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, _pwm_with(max_output_voltage_v=5.5)))


def test_required_over_max_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, _pwm_with(required_output_voltage_v=5.0, max_output_voltage_v=4.0)))


def test_missing_laser_channel_rejected(tmp_path):
    light = copy.deepcopy(PWM_LIGHT)
    del light["channels"]["laser"]
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, light))


def test_channel_index_out_of_range_rejected(tmp_path):
    light = copy.deepcopy(PWM_LIGHT)
    light["channels"]["laser"]["channel"] = 6
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, light))


def test_duplicate_channel_index_rejected(tmp_path):
    light = copy.deepcopy(PWM_LIGHT)
    light["channels"]["led"]["channel"] = 2  # same as laser
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, light))


def test_non_positive_frequency_rejected(tmp_path):
    light = copy.deepcopy(PWM_LIGHT)
    light["channels"]["laser"]["frequency_hz"] = 0
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, light))


def test_duty_out_of_range_rejected(tmp_path):
    light = copy.deepcopy(PWM_LIGHT)
    light["channels"]["laser"]["duty_percent"] = 150.0
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, light))


def test_pwm_with_manual_control_true_rejected(tmp_path):
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, _pwm_with(manual_light_control=True)))


@pytest.mark.parametrize("bad_station", [248, -1])
def test_station_id_out_of_modbus_range_rejected(tmp_path, bad_station):
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, _pwm_with(station_id=bad_station)))


def test_channel_not_default_off_required_rejected(tmp_path):
    light = copy.deepcopy(PWM_LIGHT)
    light["channels"]["laser"]["default_off_required"] = False
    with pytest.raises(ConfigError):
        load_devices_config(_write(tmp_path, light))
