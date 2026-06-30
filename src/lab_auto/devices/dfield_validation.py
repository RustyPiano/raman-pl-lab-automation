import ctypes
import math

from lab_auto.errors import ConfigError


MAX_BIN_X = 64
MAX_BIN_Y = 129


def _is_integer(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return False
    cast = ctypes.c_float(number).value
    return math.isfinite(number) and math.isfinite(cast) and cast > 0


def validate_dfield_bin_roi(
    *,
    bin_x: int,
    bin_y: int,
    roi: tuple[int, int, int, int] | None,
    detector_width: int | None = None,
    detector_height: int | None = None,
) -> None:
    if not _is_integer(bin_x) or bin_x < 1 or bin_x > MAX_BIN_X:
        raise ConfigError("DField bin_x must be between 1 and 64")
    if not _is_integer(bin_y) or bin_y < 1 or bin_y > MAX_BIN_Y:
        raise ConfigError("DField bin_y must be between 1 and 129")
    if roi is None:
        return
    if not isinstance(roi, tuple) or len(roi) != 4 or any(not _is_integer(value) for value in roi):
        raise ConfigError("DField ROI bounds are invalid")
    col_from, col_to, row_from, row_to = roi
    if col_from < 0 or row_from < 0 or col_to < col_from or row_to < row_from:
        raise ConfigError("DField ROI bounds are invalid")
    if detector_width is not None and col_to >= detector_width:
        raise ConfigError("DField ROI col_to exceeds detector width")
    if detector_height is not None and row_to >= detector_height:
        raise ConfigError("DField ROI row_to exceeds detector height")
    width = col_to - col_from + 1
    height = row_to - row_from + 1
    if width // bin_x <= 0 or height // bin_y <= 0:
        raise ConfigError("DField capture size must be positive after ROI and binning")


def validate_dfield_image_size(*, width: int, height: int, bin_x: int, bin_y: int) -> None:
    if not _is_integer(bin_x) or not _is_integer(bin_y):
        raise ConfigError("DField bin values must be integers")
    if width // bin_x <= 0 or height // bin_y <= 0:
        raise ConfigError("DField capture size must be positive after detector size and binning")


def validate_dfield_capture_args(
    *,
    read_mode: str,
    exposure_ms: float,
    gain: str,
    frames: int,
    bin_x: int = 1,
    bin_y: int = 1,
    roi: tuple[int, int, int, int] | None = None,
) -> None:
    if read_mode not in ("fvb", "image"):
        raise ConfigError(f"unsupported DField read_mode: {read_mode}")
    if read_mode == "fvb" and roi is not None:
        raise ConfigError("DField ROI is only supported for image read_mode")
    if gain not in ("high", "low"):
        raise ConfigError(f"unsupported DField gain: {gain}")
    if not _is_finite_number(exposure_ms) or exposure_ms <= 0:
        raise ConfigError("--exposure-ms must be positive")
    if not _is_integer(frames) or frames < 1:
        raise ConfigError("frames must be at least 1")
    validate_dfield_bin_roi(bin_x=bin_x, bin_y=bin_y, roi=roi)
