import pytest

from lab_auto.config import ScanPattern
from lab_auto.scan.pattern import measurement_points


def _pattern(**overrides):
    base = dict(
        repeats_per_point=2,
        burn_metric="relative_l2",
        burn_threshold=0.1,
        surrounding_count=2,
        surrounding_distance_um=10.0,
        surrounding_angles_deg=[0.0, 90.0],
    )
    base.update(overrides)
    return ScanPattern(**base)


def test_center_is_first_point():
    pts = measurement_points((100.0, 200.0), _pattern())
    assert pts[0] == (pytest.approx(100.0), pytest.approx(200.0), "center")


def test_surrounding_point_geometry():
    pts = measurement_points((0.0, 0.0), _pattern(surrounding_angles_deg=[0.0, 90.0]))
    assert len(pts) == 3
    # angle 0 -> +x
    assert pts[1][0] == pytest.approx(10.0)
    assert pts[1][1] == pytest.approx(0.0, abs=1e-9)
    assert pts[1][2] == "surrounding_0"
    # angle 90 -> +y
    assert pts[2][0] == pytest.approx(0.0, abs=1e-9)
    assert pts[2][1] == pytest.approx(10.0)
    assert pts[2][2] == "surrounding_1"


def test_angle_180_is_negative_x():
    pts = measurement_points(
        (5.0, 5.0),
        _pattern(surrounding_count=1, surrounding_angles_deg=[180.0]),
    )
    assert pts[1][0] == pytest.approx(5.0 - 10.0)
    assert pts[1][1] == pytest.approx(5.0, abs=1e-9)


def test_zero_surrounding_points_gives_only_center():
    pts = measurement_points(
        (1.0, 2.0),
        _pattern(surrounding_count=0, surrounding_angles_deg=[]),
    )
    assert pts == [(pytest.approx(1.0), pytest.approx(2.0), "center")]
