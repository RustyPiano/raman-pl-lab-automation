from lab_auto.errors import ConfigError


MAX_BIN_X = 64
MAX_BIN_Y = 129


def validate_dfield_bin_roi(
    *,
    bin_x: int,
    bin_y: int,
    roi: tuple[int, int, int, int] | None,
    detector_width: int | None = None,
    detector_height: int | None = None,
) -> None:
    if bin_x < 1 or bin_x > MAX_BIN_X:
        raise ConfigError("DField bin_x must be between 1 and 64")
    if bin_y < 1 or bin_y > MAX_BIN_Y:
        raise ConfigError("DField bin_y must be between 1 and 129")
    if roi is None:
        return
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
    if exposure_ms <= 0:
        raise ConfigError("--exposure-ms must be positive")
    if frames < 1:
        raise ConfigError("frames must be at least 1")
    validate_dfield_bin_roi(bin_x=bin_x, bin_y=bin_y, roi=roi)
