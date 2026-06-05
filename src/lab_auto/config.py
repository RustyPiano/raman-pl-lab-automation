from dataclasses import dataclass
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
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"configuration root must be a mapping: {path}")
    return data


def _as_bool(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ConfigError(f"{field} must be a boolean")


def load_devices_config(path: str | Path) -> DevicesConfig:
    data = _read_yaml(Path(path))
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
            baudrate=int(stage["baudrate"]),
            resolution_um={axis: float(value) for axis, value in stage["resolution_um"].items()},
            default_speed=int(stage["default_speed"]),
            soft_limits_um={axis: [float(v) for v in values] for axis, values in stage["soft_limits_um"].items()},
            state_file=Path(stage["state_file"]),
            max_unknown_move_um=float(stage["max_unknown_move_um"]),
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


def load_workflow_config(path: str | Path) -> WorkflowConfig:
    data = _read_yaml(Path(path))
    return WorkflowConfig(
        devices_config=Path(data["devices_config"]),
        sample=SampleConfig(**data["sample"]),
        optics=OpticsConfig(**data["optics"]),
        acquisition=AcquisitionConfig(**data["acquisition"]),
        output=OutputConfig(
            directory=Path(data["output"]["directory"]),
            formats=list(data["output"]["formats"]),
        ),
    )


def load_workflow_and_devices(
    workflow_path: str | Path,
    *,
    devices_override: str | Path | None = None,
) -> tuple[WorkflowConfig, DevicesConfig]:
    workflow = load_workflow_config(workflow_path)
    devices_path = Path(devices_override) if devices_override is not None else workflow.devices_config
    return workflow, load_devices_config(devices_path)
