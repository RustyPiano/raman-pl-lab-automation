import ctypes
import math

from lab_auto.errors import ConfigError


C_INT_MIN = -(2**31)
C_INT_MAX = 2**31 - 1


def is_integer(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _fits_c_int(value) -> bool:
    return is_integer(value) and C_INT_MIN <= value <= C_INT_MAX


def is_positive_c_float(value) -> bool:
    """value 转成 DLL 使用的 32 位 float 后仍是有限正数。"""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        cast = ctypes.c_float(value).value
    except OverflowError:
        return False
    return math.isfinite(cast) and cast > 0


def validate_zolix_optics(*, grating: int | None = None, wavelength_nm: float | None = None, slit_um: int | None = None) -> None:
    if grating is not None:
        if not _fits_c_int(grating) or grating < 1:
            raise ConfigError("grating must be at least 1")
    if wavelength_nm is not None:
        if not is_positive_c_float(wavelength_nm):
            raise ConfigError("wavelength_nm must be positive")
    if slit_um is not None:
        if not _fits_c_int(slit_um) or slit_um <= 0:
            raise ConfigError("slit_um must be positive")


def validate_zolix_pixels_to_waves_args(*, turret: int, grating: int, center_wavelength_nm: float, width: int, count: int, bin_x: int) -> None:
    if not _fits_c_int(turret):
        raise ConfigError("turret must fit signed 32-bit integer")
    if not _fits_c_int(grating) or grating < 1:
        raise ConfigError("grating must be at least 1")
    if not is_positive_c_float(center_wavelength_nm):
        raise ConfigError("center_wavelength_nm must be positive")
    if not _fits_c_int(width) or width < 1:
        raise ConfigError("width must be at least 1")
    if not _fits_c_int(count) or count < 1:
        raise ConfigError("count must be at least 1")
    if not _fits_c_int(bin_x) or bin_x < 1:
        raise ConfigError("bin_x must be at least 1")
