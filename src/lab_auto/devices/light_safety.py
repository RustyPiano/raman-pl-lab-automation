"""Pure cross-field validation for the PWM light backend configuration.

Mirrors ``optics_validation.py``: no I/O, raises ``ConfigError`` on any unsafe or
malformed setpoint. The 5.0 V cap is sourced from ``raw/pwm_modbus`` so there is a
single source of truth.
"""

import math

from lab_auto.devices.raw.pwm_modbus import MAX_VOLTAGE_DECIVOLT, register_to_voltage, voltage_to_register
from lab_auto.errors import ConfigError

MAX_OUTPUT_VOLTAGE_V = register_to_voltage(MAX_VOLTAGE_DECIVOLT)  # 5.0 V


def validate_pwm_light_config(light) -> None:
    if light.manual_light_control:
        raise ConfigError("pwm_modbus backend requires manual_light_control=false")
    if light.station_id < 1 or light.station_id > 247:
        raise ConfigError("pwm_modbus station_id must be between 1 and 247 (0 is forbidden)")
    if not (0 < light.max_output_voltage_v <= MAX_OUTPUT_VOLTAGE_V):
        raise ConfigError(f"max_output_voltage_v must be positive and not exceed {MAX_OUTPUT_VOLTAGE_V} V")
    if light.required_output_voltage_v <= 0:
        raise ConfigError("required_output_voltage_v must be positive")
    if light.required_output_voltage_v > light.max_output_voltage_v:
        raise ConfigError("required_output_voltage_v must not exceed max_output_voltage_v")
    for name, value in (
        ("max_output_voltage_v", light.max_output_voltage_v),
        ("required_output_voltage_v", light.required_output_voltage_v),
    ):
        if not math.isclose(register_to_voltage(voltage_to_register(value)), value, abs_tol=1e-9):
            raise ConfigError(f"{name} must use the controller's 0.1 V resolution")
    if not light.port:
        raise ConfigError("pwm_modbus requires a serial port")
    if light.baudrate <= 0:
        raise ConfigError("pwm_modbus baudrate must be positive")
    channels = light.channels
    if "laser" not in channels:
        raise ConfigError("pwm_modbus requires a 'laser' channel mapping")
    seen_indices: dict[int, str] = {}
    for name, channel in channels.items():
        if channel.channel < 1 or channel.channel > 5:
            raise ConfigError(f"channel index for '{name}' must be between 1 and 5")
        if channel.channel in seen_indices:
            raise ConfigError(
                f"channel index {channel.channel} is shared by '{seen_indices[channel.channel]}' and '{name}'"
            )
        seen_indices[channel.channel] = name
        if channel.frequency_hz <= 0 or channel.frequency_hz > 0xFFFFFFFF:
            raise ConfigError(f"frequency_hz for '{name}' must be between 1 and 4294967295")
        if not (0.0 <= channel.duty_percent <= 100.0):
            raise ConfigError(f"duty_percent for '{name}' must be between 0 and 100")
        if not math.isclose(round(channel.duty_percent * 10) / 10, channel.duty_percent, abs_tol=1e-9):
            raise ConfigError(f"duty_percent for '{name}' must use the controller's 0.1% resolution")
