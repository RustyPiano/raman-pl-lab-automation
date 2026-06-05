from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import yaml

from lab_auto.errors import ConfigError
from lab_auto.runtime import RuntimeMode, parse_runtime_mode


@dataclass(frozen=True)
class RuntimeConfig:
    mode: RuntimeMode
    log_level: str


@dataclass(frozen=True)
class StageConfig:
    type: str
    port: str
    baudrate: int
    resolution_um: dict[str, float]
    default_speed: int
    soft_limits_um: dict[str, list[float]]
    state_file: Path
    max_unknown_move_um: float


@dataclass(frozen=True)
class SpectrometerConfig:
    type: str
    dll_path: Path
    usb_mode: bool


@dataclass(frozen=True)
class CameraConfig:
    type: str
    dll_path: Path


@dataclass(frozen=True)
class LightConfig:
    type: str
    manual_light_control: bool


@dataclass(frozen=True)
class DevicesConfig:
    runtime: RuntimeConfig
    stage: StageConfig
    spectrometer: SpectrometerConfig
    camera: CameraConfig
    light: LightConfig


@dataclass(frozen=True)
class SampleConfig:
    id: str
    operator: str


@dataclass(frozen=True)
class OpticsConfig:
    entrance_port: str
    exit_port: str
    grating: int
    center_wavelength_nm: float
    slit_width_um: int


@dataclass(frozen=True)
class AcquisitionConfig:
    exposure_ms: float
    gain: str
    read_mode: str
    frames: int
    subtract_background: bool


@dataclass(frozen=True)
class OutputConfig:
    directory: Path
    formats: list[str]


@dataclass(frozen=True)
class WorkflowConfig:
    devices_config: Path
    sample: SampleConfig
    optics: OpticsConfig
    acquisition: AcquisitionConfig
    output: OutputConfig


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"configuration file does not exist: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (ValueError, yaml.YAMLError) as exc:
        raise ConfigError(f"configuration YAML is invalid: {path}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"configuration root must be a mapping: {path}")
    return data


def _as_bool(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigError(f"{field} must be a boolean")


def _finite_float(value: Any, *, field: str) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"{field} must be finite")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ConfigError(f"{field} must be finite") from exc
    if not math.isfinite(number):
        raise ConfigError(f"{field} must be finite")
    return number


def _finite_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ConfigError(f"{field} must be an integer")
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text or text[0] in "+-" and len(text) == 1:
            raise ConfigError(f"{field} must be an integer")
        digits = text[1:] if text[0] in "+-" else text
        if not digits.isdigit():
            raise ConfigError(f"{field} must be an integer")
        try:
            return int(text)
        except ValueError as exc:
            raise ConfigError(f"{field} must be an integer") from exc
    number = _finite_float(value, field=field)
    if not number.is_integer():
        raise ConfigError(f"{field} must be an integer")
    return int(number)


def _resolution_um(value: Any) -> dict[str, float]:
    resolution = {axis: _finite_float(item, field=f"resolution_um.{axis}") for axis, item in value.items()}
    for axis, item in resolution.items():
        if item <= 0:
            raise ConfigError(f"resolution_um.{axis} must be positive")
    return resolution


def _soft_limits_um(value: Any) -> dict[str, list[float]]:
    limits = {}
    for axis, axis_limits in value.items():
        if not isinstance(axis_limits, (list, tuple)) or len(axis_limits) != 2:
            raise ConfigError(f"soft_limits_um.{axis} must contain two bounds")
        low, high = [_finite_float(item, field=f"soft_limits_um.{axis}") for item in axis_limits]
        if low > high:
            raise ConfigError(f"soft_limits_um.{axis} lower bound must be <= upper bound")
        limits[axis] = [low, high]
    return limits


def load_devices_config(path: str | Path) -> DevicesConfig:
    config_path = Path(path)
    data = _read_yaml(config_path)
    try:
        runtime = data.get("runtime", {})
        stage = data["stage"]
        spectrometer = data["spectrometer"]
        camera = data["camera"]
        light = data["light"]
        return DevicesConfig(
            runtime=RuntimeConfig(
                mode=parse_runtime_mode(runtime.get("mode")),
                log_level=str(runtime.get("log_level", "info")),
            ),
            stage=StageConfig(
                type=str(stage["type"]),
                port=str(stage["port"]),
                baudrate=_finite_int(stage["baudrate"], field="baudrate"),
                resolution_um=_resolution_um(stage["resolution_um"]),
                default_speed=_finite_int(stage["default_speed"], field="default_speed"),
                soft_limits_um=_soft_limits_um(stage["soft_limits_um"]),
                state_file=Path(stage["state_file"]),
                max_unknown_move_um=_finite_float(stage["max_unknown_move_um"], field="max_unknown_move_um"),
            ),
            spectrometer=SpectrometerConfig(
                type=str(spectrometer["type"]),
                dll_path=Path(spectrometer["dll_path"]),
                usb_mode=_as_bool(spectrometer.get("usb_mode", True), field="usb_mode"),
            ),
            camera=CameraConfig(type=str(camera["type"]), dll_path=Path(camera["dll_path"])),
            light=LightConfig(
                type=str(light["type"]),
                manual_light_control=_as_bool(light["manual_light_control"], field="manual_light_control"),
            ),
        )
    except KeyError as exc:
        raise ConfigError(f"missing required devices configuration field: {exc.args[0]} in {config_path}") from exc
    except (AttributeError, TypeError, ValueError) as exc:
        raise ConfigError(f"invalid devices configuration in {config_path}: {exc}") from exc


def load_workflow_config(path: str | Path) -> WorkflowConfig:
    config_path = Path(path)
    data = _read_yaml(config_path)
    try:
        sample = data["sample"]
        optics = data["optics"]
        acquisition = data["acquisition"]
        output = data["output"]
        formats = output["formats"]
        if not isinstance(formats, list):
            raise ConfigError(f"output.formats must be a list in {config_path}")
        return WorkflowConfig(
            devices_config=Path(data["devices_config"]),
            sample=SampleConfig(id=str(sample["id"]), operator=str(sample["operator"])),
            optics=OpticsConfig(
                entrance_port=str(optics["entrance_port"]),
                exit_port=str(optics["exit_port"]),
                grating=_finite_int(optics["grating"], field="grating"),
                center_wavelength_nm=_finite_float(optics["center_wavelength_nm"], field="center_wavelength_nm"),
                slit_width_um=_finite_int(optics["slit_width_um"], field="slit_width_um"),
            ),
            acquisition=AcquisitionConfig(
                exposure_ms=_finite_float(acquisition["exposure_ms"], field="exposure_ms"),
                gain=str(acquisition["gain"]),
                read_mode=str(acquisition["read_mode"]),
                frames=_finite_int(acquisition["frames"], field="frames"),
                subtract_background=_as_bool(acquisition["subtract_background"], field="subtract_background"),
            ),
            output=OutputConfig(
                directory=Path(output["directory"]),
                formats=[str(item) for item in formats],
            ),
        )
    except KeyError as exc:
        raise ConfigError(f"missing required workflow configuration field: {exc.args[0]} in {config_path}") from exc
    except (AttributeError, TypeError, ValueError) as exc:
        raise ConfigError(f"invalid workflow configuration in {config_path}: {exc}") from exc


def load_workflow_and_devices(
    workflow_path: str | Path,
    *,
    devices_override: str | Path | None = None,
) -> tuple[WorkflowConfig, DevicesConfig]:
    workflow = load_workflow_config(workflow_path)
    devices_path = Path(devices_override) if devices_override is not None else workflow.devices_config
    return workflow, load_devices_config(devices_path)
