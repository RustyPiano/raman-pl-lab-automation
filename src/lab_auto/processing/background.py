from lab_auto.errors import ConfigError
from lab_auto.workflow.data import SpectrumData


AXIS_METADATA_KEYS = (
    "read_mode",
    "bin_x",
    "bin_y",
    "roi",
    "detector_width",
    "detector_height",
    "grating",
    "center_wavelength_nm",
    "slit_width_um",
)


def _assert_axis_metadata_matches(raw: SpectrumData, background: SpectrumData) -> None:
    for key in AXIS_METADATA_KEYS:
        if raw.metadata.get(key) != background.metadata.get(key):
            raise ConfigError(f"axis metadata differs: {key}")


def _assert_x_matches(raw: SpectrumData, background: SpectrumData, wavelength_tolerance_nm: float) -> None:
    if raw.x_axis_type != background.x_axis_type:
        raise ConfigError("x_axis_type differs between raw and background spectra")
    if len(raw.x) != len(background.x):
        raise ConfigError("raw/background lengths differ")
    for index, (raw_x, bg_x) in enumerate(zip(raw.x, background.x, strict=True)):
        if raw.x_axis_type == "pixel_index":
            if int(raw_x) != int(bg_x):
                raise ConfigError(f"x axis values differ at index {index}")
        elif abs(float(raw_x) - float(bg_x)) > wavelength_tolerance_nm:
            raise ConfigError(f"x axis values differ at index {index}")


def subtract_background(
    raw: SpectrumData,
    background: SpectrumData,
    *,
    wavelength_tolerance_nm: float = 1e-6,
) -> SpectrumData:
    _assert_x_matches(raw, background, wavelength_tolerance_nm)
    _assert_axis_metadata_matches(raw, background)
    corrected = [
        float(raw_value) - float(bg_value)
        for raw_value, bg_value in zip(raw.intensity_raw, background.intensity_raw, strict=True)
    ]
    return raw.with_background(background.intensity_raw, corrected, background.saturated)
