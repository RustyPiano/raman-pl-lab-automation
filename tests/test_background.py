import pytest

from lab_auto.errors import ConfigError
from lab_auto.processing.background import subtract_background
from lab_auto.workflow.data import SpectrumData


def spectrum(*, x, raw, background=None, metadata=None):
    return SpectrumData(
        x_axis_type="wavelength_nm",
        x=list(x),
        intensity_raw=list(raw),
        intensity_background=background,
        intensity_corrected=None,
        saturated=[False for _ in raw],
        metadata=metadata
        or {
            "read_mode": "fvb",
            "bin_x": 1,
            "bin_y": 1,
            "roi": None,
            "detector_width": 2048,
            "detector_height": 1,
            "grating": 1,
            "center_wavelength_nm": 600.0,
            "slit_width_um": 100,
        },
    )


def test_subtract_background_aligns_by_x_values():
    raw = spectrum(x=[580.0, 581.0], raw=[1000, 1100])
    bg = spectrum(x=[580.0, 581.0], raw=[100, 120])

    corrected = subtract_background(raw, bg)

    assert corrected.intensity_background == [100, 120]
    assert corrected.intensity_corrected == [900, 980]


def test_subtract_background_rejects_wavelength_mismatch():
    raw = spectrum(x=[580.0, 581.0], raw=[1000, 1100])
    bg = spectrum(x=[580.0, 581.002], raw=[100, 120])

    with pytest.raises(ConfigError, match="x axis values differ"):
        subtract_background(raw, bg, wavelength_tolerance_nm=1e-6)


def test_subtract_background_rejects_axis_metadata_mismatch():
    raw = spectrum(x=[580.0], raw=[1000])
    bg = spectrum(
        x=[580.0],
        raw=[100],
        metadata={
            "read_mode": "fvb",
            "bin_x": 2,
            "bin_y": 1,
            "roi": None,
            "detector_width": 2048,
            "detector_height": 1,
            "grating": 1,
            "center_wavelength_nm": 600.0,
            "slit_width_um": 100,
        },
    )

    with pytest.raises(ConfigError, match="axis metadata differs: bin_x"):
        subtract_background(raw, bg)
