from lab_auto.errors import ConfigError


def validate_zolix_optics(*, grating: int | None = None, wavelength_nm: float | None = None, slit_um: int | None = None) -> None:
    if grating is not None and grating < 1:
        raise ConfigError("grating must be at least 1")
    if wavelength_nm is not None and wavelength_nm <= 0:
        raise ConfigError("wavelength_nm must be positive")
    if slit_um is not None and slit_um <= 0:
        raise ConfigError("slit_um must be positive")
