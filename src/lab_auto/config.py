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
    home_direction: dict[str, str] | None = None


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
class PwmChannel:
    channel: int
    frequency_hz: int
    duty_percent: float
    default_off_required: bool


@dataclass(frozen=True)
class LightConfig:
    type: str
    manual_light_control: bool
    port: str | None = None
    station_id: int | None = None
    baudrate: int | None = None
    max_output_voltage_v: float | None = None
    required_output_voltage_v: float | None = None
    channels: dict[str, PwmChannel] | None = None


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


@dataclass(frozen=True)
class Calibration:
    """Per-objective affine pixel->stage calibration.

    ``a11..a22`` are the ``A`` matrix (um-per-pixel) mapping an image-shift
    request ``(image_center - pixel)`` to a relative stage move; the image
    center is the coordinate origin (= laser spot at capture).
    """

    objective: str
    a11: float
    a12: float
    a21: float
    a22: float
    image_center_px: float
    image_center_py: float
    # Declared capture pixel space this calibration was measured in. When set, the
    # tray scan asserts every recognition mask matches it — a mask at a different
    # resolution (e.g. a model that resized) would otherwise map centroids to the
    # wrong stage µm and drive the laser off-target. Optional for back-compat.
    image_width_px: int | None = None
    image_height_px: int | None = None


@dataclass(frozen=True)
class TrayLayout:
    """Sample-tray grid geometry (wafer-center coords from known geometry)."""

    rows: int
    cols: int
    pitch_x_um: float
    pitch_y_um: float
    first_cell_offset_x_um: float
    first_cell_offset_y_um: float
    order: str


@dataclass(frozen=True)
class ScanPattern:
    """Per-center measurement pattern: center + parameterized surrounding points.

    Each point's single-point Raman is repeated ``repeats_per_point`` times as a
    BURN CHECK (compared, flagged), not averaged.
    """

    repeats_per_point: int
    burn_metric: str
    burn_threshold: float
    surrounding_count: int
    surrounding_distance_um: float
    surrounding_angles_deg: list[float]


@dataclass(frozen=True)
class TrayScanConfig:
    devices_config: Path
    sample: SampleConfig
    optics: OpticsConfig
    acquisition: AcquisitionConfig
    output: OutputConfig
    tray: TrayLayout
    pattern: ScanPattern
    calibration: Calibration
    min_area: int
    on_out_of_range: str


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"configuration file does not exist: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
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


_REQUIRED_AXES = ("x", "y")


def _resolution_um(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ConfigError("resolution_um must be a mapping")
    resolution = {axis: _finite_float(item, field=f"resolution_um.{axis}") for axis, item in value.items()}
    for axis, item in resolution.items():
        if item <= 0:
            raise ConfigError(f"resolution_um.{axis} must be positive")
    return resolution


def _soft_limits_um(value: Any) -> dict[str, list[float]]:
    if not isinstance(value, dict):
        raise ConfigError("soft_limits_um must be a mapping")
    limits = {}
    for axis, axis_limits in value.items():
        if not isinstance(axis_limits, (list, tuple)) or len(axis_limits) != 2:
            raise ConfigError(f"soft_limits_um.{axis} must contain two bounds")
        low, high = [_finite_float(item, field=f"soft_limits_um.{axis}") for item in axis_limits]
        if low >= high:
            raise ConfigError(f"soft_limits_um.{axis} lower bound must be < upper bound")
        if not low <= 0 <= high:
            raise ConfigError(f"soft_limits_um.{axis} must contain the homed/user-zero origin 0")
        limits[axis] = [low, high]
    return limits


def _parse_home_direction(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ConfigError("stage home_direction must map each configured axis to 'positive' or 'negative'")
    directions = {str(axis): str(direction) for axis, direction in value.items()}
    invalid = {axis: direction for axis, direction in directions.items() if direction not in ("positive", "negative")}
    if invalid:
        raise ConfigError(f"stage home_direction contains invalid directions: {invalid}")
    return directions


def _validate_stage_axes(
    resolution: dict[str, float],
    soft_limits: dict[str, list[float]],
    home_direction: dict[str, str] | None,
) -> None:
    unsupported = set(resolution) - {"x", "y", "z"}
    if unsupported:
        raise ConfigError(f"stage contains unsupported axes: {sorted(unsupported)}")
    for field, mapping in (("resolution_um", resolution), ("soft_limits_um", soft_limits)):
        missing = [axis for axis in _REQUIRED_AXES if axis not in mapping]
        if missing:
            raise ConfigError(f"stage {field} is missing required axes: {missing}")
    if resolution.keys() != soft_limits.keys():
        raise ConfigError(
            f"stage resolution_um axes {sorted(resolution)} must match soft_limits_um axes {sorted(soft_limits)}"
        )
    if home_direction is not None and home_direction.keys() != resolution.keys():
        raise ConfigError(
            f"stage home_direction axes {sorted(home_direction)} must match configured stage axes {sorted(resolution)}"
        )


def _parse_pwm_channel(name: str, value: Any) -> PwmChannel:
    if not isinstance(value, dict):
        raise ConfigError(f"light.channels.{name} must be a mapping")
    return PwmChannel(
        channel=_finite_int(value["channel"], field=f"channels.{name}.channel"),
        frequency_hz=_finite_int(value["frequency_hz"], field=f"channels.{name}.frequency_hz"),
        duty_percent=_finite_float(value["duty_percent"], field=f"channels.{name}.duty_percent"),
        default_off_required=_as_bool(value.get("default_off_required", True), field=f"channels.{name}.default_off_required"),
    )


def _parse_light(light: dict[str, Any]) -> LightConfig:
    light_type = str(light["type"])
    manual_control = _as_bool(light["manual_light_control"], field="manual_light_control")
    if light_type == "manual":
        if not manual_control:
            raise ConfigError("manual light requires manual_light_control=true")
        return LightConfig(type=light_type, manual_light_control=manual_control)
    if light_type == "pwm_modbus":
        from lab_auto.devices.light_safety import validate_pwm_light_config

        channels_raw = light.get("channels")
        if not isinstance(channels_raw, dict):
            raise ConfigError("pwm_modbus light requires a 'channels' mapping")
        channels = {name: _parse_pwm_channel(name, value) for name, value in channels_raw.items()}
        config = LightConfig(
            type=light_type,
            manual_light_control=manual_control,
            port=str(light["port"]),
            station_id=_finite_int(light["station_id"], field="station_id"),
            baudrate=_finite_int(light.get("baudrate", 9600), field="baudrate"),
            max_output_voltage_v=_finite_float(light["max_output_voltage_v"], field="max_output_voltage_v"),
            required_output_voltage_v=_finite_float(light["required_output_voltage_v"], field="required_output_voltage_v"),
            channels=channels,
        )
        validate_pwm_light_config(config)
        return config
    raise ConfigError(f"unsupported light type: {light_type}")


def load_devices_config(path: str | Path) -> DevicesConfig:
    config_path = Path(path)
    data = _read_yaml(config_path)
    try:
        runtime = data.get("runtime", {})
        stage = data["stage"]
        spectrometer = data["spectrometer"]
        camera = data["camera"]
        light = data["light"]
        resolution_um = _resolution_um(stage["resolution_um"])
        soft_limits_um = _soft_limits_um(stage["soft_limits_um"])
        home_direction = _parse_home_direction(stage.get("home_direction"))
        _validate_stage_axes(resolution_um, soft_limits_um, home_direction)
        stage_type = str(stage["type"])
        stage_port = str(stage["port"])
        baudrate = _finite_int(stage["baudrate"], field="baudrate")
        default_speed = _finite_int(stage["default_speed"], field="default_speed")
        max_unknown_move_um = _finite_float(stage["max_unknown_move_um"], field="max_unknown_move_um")
        state_file = str(stage["state_file"])
        spectrometer_type = str(spectrometer["type"])
        camera_type = str(camera["type"])
        if stage_type != "waynelabs_linear":
            raise ConfigError(f"unsupported stage type: {stage_type}")
        if spectrometer_type != "zolix":
            raise ConfigError(f"unsupported spectrometer type: {spectrometer_type}")
        if camera_type != "dfield_vs_a4":
            raise ConfigError(f"unsupported camera type: {camera_type}")
        if not stage_port.strip():
            raise ConfigError("stage port cannot be empty")
        if baudrate <= 0:
            raise ConfigError("stage baudrate must be positive")
        if not 0 <= default_speed <= 9:
            raise ConfigError("stage default_speed must be between 0 and 9")
        if max_unknown_move_um < 0:
            raise ConfigError("stage max_unknown_move_um cannot be negative")
        if not state_file.strip():
            raise ConfigError("stage state_file cannot be empty")
        return DevicesConfig(
            runtime=RuntimeConfig(
                mode=parse_runtime_mode(runtime.get("mode")),
                log_level=str(runtime.get("log_level", "info")),
            ),
            stage=StageConfig(
                type=stage_type,
                port=stage_port,
                baudrate=baudrate,
                resolution_um=resolution_um,
                default_speed=default_speed,
                soft_limits_um=soft_limits_um,
                state_file=Path(state_file),
                max_unknown_move_um=max_unknown_move_um,
                home_direction=home_direction,
            ),
            spectrometer=SpectrometerConfig(
                type=spectrometer_type,
                dll_path=Path(spectrometer["dll_path"]),
                usb_mode=_as_bool(spectrometer.get("usb_mode", True), field="usb_mode"),
            ),
            camera=CameraConfig(type=camera_type, dll_path=Path(camera["dll_path"])),
            light=_parse_light(light),
        )
    except KeyError as exc:
        raise ConfigError(f"missing required devices configuration field: {exc.args[0]} in {config_path}") from exc
    except (AttributeError, TypeError, ValueError) as exc:
        raise ConfigError(f"invalid devices configuration in {config_path}: {exc}") from exc


def validate_sample_id(sample_id: str) -> str:
    """Reject a sample.id that isn't a safe single filename token.

    It becomes a filesystem path component (run dir / manifest), so '../x' or
    'a/b' would escape the output directory. Public so any layer that supplies an
    id out-of-band (for example, an API override) can re-apply the same guard.
    """
    invalid_chars = '<>:"/\\|?*'
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    stem = sample_id.split(".", 1)[0].upper()
    if (
        not sample_id
        or len(sample_id) > 128
        or sample_id != sample_id.strip()
        or sample_id in (".", "..")
        or sample_id[-1] in (" ", ".")
        or stem in reserved
        or any(ch in invalid_chars or ord(ch) < 32 for ch in sample_id)
    ):
        raise ConfigError(f"sample.id must be a Windows-safe filename token: {sample_id!r}")
    return sample_id


def _parse_sample(sample: Any) -> SampleConfig:
    if sample["id"] is None or sample["operator"] is None:
        raise ConfigError("sample.id and sample.operator cannot be null")
    operator = str(sample["operator"]).strip()
    if not operator:
        raise ConfigError("sample.operator cannot be empty")
    return SampleConfig(id=validate_sample_id(str(sample["id"])), operator=operator)


def _parse_optics(optics: Any) -> OpticsConfig:
    return OpticsConfig(
        entrance_port=str(optics["entrance_port"]),
        exit_port=str(optics["exit_port"]),
        grating=_finite_int(optics["grating"], field="grating"),
        center_wavelength_nm=_finite_float(optics["center_wavelength_nm"], field="center_wavelength_nm"),
        slit_width_um=_finite_int(optics["slit_width_um"], field="slit_width_um"),
    )


def _parse_acquisition(acquisition: Any) -> AcquisitionConfig:
    return AcquisitionConfig(
        exposure_ms=_finite_float(acquisition["exposure_ms"], field="exposure_ms"),
        gain=str(acquisition["gain"]),
        read_mode=str(acquisition["read_mode"]),
        frames=_finite_int(acquisition["frames"], field="frames"),
        subtract_background=_as_bool(acquisition["subtract_background"], field="subtract_background"),
    )


def _parse_output(output: Any) -> OutputConfig:
    formats = output["formats"]
    if not isinstance(formats, list):
        raise ConfigError("output.formats must be a list")
    normalized = [str(item).lower() for item in formats]
    if len(normalized) != 2 or set(normalized) != {"csv", "json"}:
        raise ConfigError("output.formats must contain exactly [csv, json]; both workflow outputs are required")
    return OutputConfig(
        directory=Path(output["directory"]),
        formats=normalized,
    )


def load_workflow_config(path: str | Path) -> WorkflowConfig:
    config_path = Path(path)
    data = _read_yaml(config_path)
    try:
        return WorkflowConfig(
            devices_config=Path(data["devices_config"]),
            sample=_parse_sample(data["sample"]),
            optics=_parse_optics(data["optics"]),
            acquisition=_parse_acquisition(data["acquisition"]),
            output=_parse_output(data["output"]),
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


def _parse_tray(tray: Any) -> TrayLayout:
    layout = TrayLayout(
        rows=_finite_int(tray["rows"], field="tray.rows"),
        cols=_finite_int(tray["cols"], field="tray.cols"),
        pitch_x_um=_finite_float(tray["pitch_x_um"], field="tray.pitch_x_um"),
        pitch_y_um=_finite_float(tray["pitch_y_um"], field="tray.pitch_y_um"),
        first_cell_offset_x_um=_finite_float(tray["first_cell_offset_x_um"], field="tray.first_cell_offset_x_um"),
        first_cell_offset_y_um=_finite_float(tray["first_cell_offset_y_um"], field="tray.first_cell_offset_y_um"),
        order=str(tray["order"]),
    )
    if layout.rows <= 0 or layout.cols <= 0:
        raise ConfigError("tray.rows and tray.cols must be positive")
    if layout.pitch_x_um <= 0 or layout.pitch_y_um <= 0:
        raise ConfigError("tray pitch must be positive")
    if layout.order not in ("row_major", "serpentine"):
        raise ConfigError(f"unknown tray.order: {layout.order!r}")
    return layout


def _parse_pattern(pattern: Any) -> ScanPattern:
    angles = pattern["surrounding_angles_deg"]
    if not isinstance(angles, list):
        raise ConfigError("pattern.surrounding_angles_deg must be a list")
    result = ScanPattern(
        repeats_per_point=_finite_int(pattern["repeats_per_point"], field="pattern.repeats_per_point"),
        burn_metric=str(pattern["burn_metric"]),
        burn_threshold=_finite_float(pattern["burn_threshold"], field="pattern.burn_threshold"),
        surrounding_count=_finite_int(pattern["surrounding_count"], field="pattern.surrounding_count"),
        surrounding_distance_um=_finite_float(pattern["surrounding_distance_um"], field="pattern.surrounding_distance_um"),
        surrounding_angles_deg=[_finite_float(a, field="pattern.surrounding_angles_deg") for a in angles],
    )
    if result.repeats_per_point < 2:
        raise ConfigError("pattern.repeats_per_point must be >= 2 for a burn check")
    if result.burn_threshold <= 0:
        # A threshold of 0 would flag every point as burned (any nonzero deviation
        # between repeats exceeds it), silently poisoning the whole manifest.
        raise ConfigError("pattern.burn_threshold must be > 0")
    if result.surrounding_count != len(result.surrounding_angles_deg):
        raise ConfigError("pattern.surrounding_count must equal len(surrounding_angles_deg)")
    if result.surrounding_count > 0 and result.surrounding_distance_um <= 0:
        raise ConfigError("pattern.surrounding_distance_um must be positive")
    if result.burn_metric != "relative_l2":
        raise ConfigError(f"unknown pattern.burn_metric: {result.burn_metric!r}")
    return result


def workflow_config_from_tray_scan(scan_config: "TrayScanConfig") -> WorkflowConfig:
    """Adapt a tray-scan config's per-point fields to a single-point WorkflowConfig.

    The tray scan reuses the single-point optics/acquisition primitive, so the
    same validation applies to each measurement point.
    """
    return WorkflowConfig(
        devices_config=scan_config.devices_config,
        sample=scan_config.sample,
        optics=scan_config.optics,
        acquisition=scan_config.acquisition,
        output=scan_config.output,
    )


def _parse_calibration(calibration: Any) -> Calibration:
    width = calibration.get("image_width_px")
    height = calibration.get("image_height_px")
    result = Calibration(
        objective=str(calibration["objective"]),
        a11=_finite_float(calibration["a11"], field="calibration.a11"),
        a12=_finite_float(calibration["a12"], field="calibration.a12"),
        a21=_finite_float(calibration["a21"], field="calibration.a21"),
        a22=_finite_float(calibration["a22"], field="calibration.a22"),
        image_center_px=_finite_float(calibration["image_center_px"], field="calibration.image_center_px"),
        image_center_py=_finite_float(calibration["image_center_py"], field="calibration.image_center_py"),
        image_width_px=_finite_int(width, field="calibration.image_width_px") if width is not None else None,
        image_height_px=_finite_int(height, field="calibration.image_height_px") if height is not None else None,
    )
    det = result.a11 * result.a22 - result.a12 * result.a21
    scale = max(abs(result.a11), abs(result.a12), abs(result.a21), abs(result.a22), 1.0)
    if abs(det) <= 1e-12 * scale * scale:
        raise ConfigError("calibration matrix is singular or near-singular (determinant ~ 0)")
    for axis, value in (("image_width_px", result.image_width_px), ("image_height_px", result.image_height_px)):
        if value is not None and value <= 0:
            raise ConfigError(f"calibration.{axis} must be positive")
    if (result.image_width_px is None) != (result.image_height_px is None):
        raise ConfigError("calibration image_width_px and image_height_px must be set together")
    if result.image_width_px is not None:
        if not 0 <= result.image_center_px < result.image_width_px:
            raise ConfigError("calibration.image_center_px must be inside the declared image width")
        if not 0 <= result.image_center_py < result.image_height_px:
            raise ConfigError("calibration.image_center_py must be inside the declared image height")
    return result


def load_tray_scan_config(path: str | Path) -> TrayScanConfig:
    config_path = Path(path)
    data = _read_yaml(config_path)
    try:
        min_area = _finite_int(data.get("min_area", 1), field="min_area")
        if min_area < 1:
            raise ConfigError("min_area must be >= 1")
        on_out_of_range = str(data["on_out_of_range"])
        if on_out_of_range not in ("skip", "abort"):
            raise ConfigError(f"unknown on_out_of_range: {on_out_of_range!r} (use skip|abort)")
        return TrayScanConfig(
            devices_config=Path(data["devices_config"]),
            sample=_parse_sample(data["sample"]),
            optics=_parse_optics(data["optics"]),
            acquisition=_parse_acquisition(data["acquisition"]),
            output=_parse_output(data["output"]),
            tray=_parse_tray(data["tray"]),
            pattern=_parse_pattern(data["pattern"]),
            calibration=_parse_calibration(data["calibration"]),
            min_area=min_area,
            on_out_of_range=on_out_of_range,
        )
    except KeyError as exc:
        raise ConfigError(f"missing required tray-scan configuration field: {exc.args[0]} in {config_path}") from exc
    except (AttributeError, TypeError, ValueError) as exc:
        raise ConfigError(f"invalid tray-scan configuration in {config_path}: {exc}") from exc
