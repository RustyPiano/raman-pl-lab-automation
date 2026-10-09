import pytest

from lab_auto.config import TrayLayout
from lab_auto.scan.tray import WaferCenter, wafer_centers


def _layout(**overrides):
    base = dict(
        rows=2,
        cols=3,
        pitch_x_um=1000.0,
        pitch_y_um=800.0,
        first_cell_offset_x_um=50.0,
        first_cell_offset_y_um=20.0,
        order="row_major",
    )
    base.update(overrides)
    return TrayLayout(**base)


def test_row_major_coordinates():
    centers = wafer_centers(_layout())
    assert len(centers) == 6
    first = centers[0]
    assert isinstance(first, WaferCenter)
    assert first.x_um == pytest.approx(50.0)
    assert first.y_um == pytest.approx(20.0)
    assert first.row == 0 and first.col == 0 and first.index == 0
    # row 0, col 2
    assert centers[2].x_um == pytest.approx(50.0 + 2 * 1000.0)
    assert centers[2].y_um == pytest.approx(20.0)
    # row 1, col 0
    assert centers[3].x_um == pytest.approx(50.0)
    assert centers[3].y_um == pytest.approx(20.0 + 800.0)


def test_row_major_visiting_order():
    centers = wafer_centers(_layout())
    seq = [(c.row, c.col) for c in centers]
    assert seq == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]


def test_serpentine_reverses_alternate_rows():
    centers = wafer_centers(_layout(order="serpentine"))
    seq = [(c.row, c.col) for c in centers]
    assert seq == [(0, 0), (0, 1), (0, 2), (1, 2), (1, 1), (1, 0)]
    # coordinates still computed from (row, col), independent of visit order
    last = centers[-1]
    assert last.row == 1 and last.col == 0
    assert last.x_um == pytest.approx(50.0)
    assert last.y_um == pytest.approx(20.0 + 800.0)
    assert [c.index for c in centers] == [0, 1, 2, 3, 4, 5]
