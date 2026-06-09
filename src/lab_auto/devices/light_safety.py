"""Pure cross-field validation for the PWM light backend configuration.

Mirrors ``optics_validation.py``: no I/O, raises ``ConfigError`` on any unsafe or
malformed setpoint. The 5.0 V cap is sourced from ``raw/pwm_modbus`` so there is a
single source of truth.
"""

from lab_auto.devices.raw.pwm_modbus import MAX_VOLTAGE_DECIVOLT, register_to_voltage
from lab_auto.errors import ConfigError

MAX_OUTPUT_VOLTAGE_V = register_to_voltage(MAX_VOLTAGE_DECIVOLT)  # 5.0 V


def validate_pwm_light_config(light) -> None:
    if light.manual_light_control:
        raise ConfigError("pwm_modbus backend requires manual_light_control=false")
    if light.station_id is None or light.station_id < 1 or light.station_id > 247:
        raise ConfigError("pwm_modbus station_id must be between 1 and 247 (0 is forbidden)")
    if light.max_output_voltage_v is None or light.max_output_voltage_v > MAX_OUTPUT_VOLTAGE_V:
        raise ConfigError(f"max_output_voltage_v must not exceed {MAX_OUTPUT_VOLTAGE_V} V")
    if light.required_output_voltage_v is None:
        raise ConfigError("pwm_modbus requires required_output_voltage_v")
    if light.required_output_voltage_v > light.max_output_voltage_v:
        raise ConfigError("required_output_voltage_v must not exceed max_output_voltage_v")
    if not light.port:
        raise ConfigError("pwm_modbus requires a serial port")
    channels = light.channels or {}
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
        if channel.frequency_hz <= 0:
            raise ConfigError(f"frequency_hz for '{name}' must be positive")
        if not (0.0 <= channel.duty_percent <= 100.0):
            raise ConfigError(f"duty_percent for '{name}' must be between 0 and 100")
        if channel.default_off_required is not True:
            raise ConfigError(f"channel '{name}' must set default_off_required: true")
