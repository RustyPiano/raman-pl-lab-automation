from types import SimpleNamespace

import pytest

from lab_auto.errors import ConfigError
from lab_auto.vision.mask_centers import extract_centers
from lab_auto.vision.recognition import FileMaskProvider, _grid_from_pixels, load_mask


def test_grid_threshold_rejects_below_and_keeps_above():
    # default-style threshold 127: 100 -> background, 200 -> foreground.
    grid = _grid_from_pixels([100, 200, 0, 255], width=2, threshold=127)
    assert grid == [[0, 1], [0, 1]]


def test_grid_ragged_width_raises():
    with pytest.raises(ConfigError):
        _grid_from_pixels([0, 1, 0], width=2, threshold=0)


def test_load_mask_missing_file_is_config_error():
    with pytest.raises(ConfigError):
        load_mask("/no/such/mask.png")


def test_file_provider_bad_pattern_field_is_config_error():
    # A pattern field other than index/row/col must fail loud (not raw KeyError).
    provider = FileMaskProvider("/tmp", pattern="{wafer}.png")
    with pytest.raises(ConfigError):
        provider(SimpleNamespace(index=0, row=0, col=0))


def test_file_provider_malformed_pattern_is_config_error():
    # A syntactically malformed format string must not leak a raw ValueError.
    provider = FileMaskProvider("/tmp", pattern="{")
    with pytest.raises(ConfigError):
        provider(SimpleNamespace(index=0, row=0, col=0))


def test_load_mask_corrupt_png_is_config_error(tmp_path):
    pytest.importorskip("PIL")
    bad = tmp_path / "half.png"
    bad.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)  # PNG signature then garbage
    with pytest.raises(ConfigError):
        load_mask(bad)


def test_load_mask_binary_png_roundtrips(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    # 0/255 mask: one foreground pixel; threshold 127 keeps it, extract finds 1 center.
    img = Image.new("L", (3, 2), 0)
    img.putpixel((1, 0), 255)
    path = tmp_path / "m.png"
    img.save(path)
    mask = load_mask(path)
    assert mask == [[0, 1, 0], [0, 0, 0]]
    assert len(extract_centers(mask)) == 1
