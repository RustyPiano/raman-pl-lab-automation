import math

import pytest

from lab_auto.config import Calibration
from lab_auto.errors import ConfigError
from lab_auto.vision.calibration import (
    fit_affine,
    mat_inverse_2x2,
    pixel_to_stage_delta,
)


def _matvec(m, v):
    return (
        m[0][0] * v[0] + m[0][1] * v[1],
        m[1][0] * v[0] + m[1][1] * v[1],
    )


def test_fit_affine_recovers_known_matrix():
    # A = um-per-pixel: 0.5 scale + small rotation.
    theta = 0.1
    s = 0.5
    A = [
        [s * math.cos(theta), -s * math.sin(theta)],
        [s * math.sin(theta), s * math.cos(theta)],
    ]
    B = mat_inverse_2x2(A)  # pixels-per-um
    # Non-colinear commanded stage moves (um).
    stage_moves = [(10.0, 0.0), (0.0, 10.0), (5.0, 7.0)]
    samples = [(S, _matvec(B, S)) for S in stage_moves]
    fitted = fit_affine(samples)
    for i in range(2):
        for j in range(2):
            assert fitted[i][j] == pytest.approx(A[i][j], abs=1e-9)


def test_fit_affine_requires_two_independent_samples():
    # Colinear stage moves -> singular -> ConfigError.
    samples = [((10.0, 0.0), (20.0, 0.0)), ((5.0, 0.0), (10.0, 0.0))]
    with pytest.raises(ConfigError):
        fit_affine(samples)


def test_pixel_to_stage_delta_at_center_is_zero():
    calib = Calibration(
        objective="50x",
        a11=0.5,
        a12=0.0,
        a21=0.0,
        a22=0.5,
        image_center_px=320.0,
        image_center_py=240.0,
    )
    dx, dy = pixel_to_stage_delta(calib, (320.0, 240.0))
    assert dx == pytest.approx(0.0)
    assert dy == pytest.approx(0.0)


def test_pixel_to_stage_delta_applies_A_to_center_minus_pixel():
    calib = Calibration(
        objective="50x",
        a11=0.5,
        a12=0.0,
        a21=0.0,
        a22=2.0,
        image_center_px=100.0,
        image_center_py=100.0,
    )
    # pixel below-right of center -> (c - p) = (-10, -20)
    dx, dy = pixel_to_stage_delta(calib, (110.0, 120.0))
    assert dx == pytest.approx(0.5 * -10.0)
    assert dy == pytest.approx(2.0 * -20.0)


def test_mat_inverse_singular_raises():
    with pytest.raises(ConfigError):
        mat_inverse_2x2([[1.0, 2.0], [2.0, 4.0]])


def test_near_singular_matrix_rejected():
    # tiny determinant relative to scale -> rejected (would blow up um/pixel coeffs)
    with pytest.raises(ConfigError):
        mat_inverse_2x2([[1.0, 1.0], [1.0, 1.0 + 1e-15]])


def test_non_finite_matrix_rejected():
    with pytest.raises(ConfigError):
        mat_inverse_2x2([[float("inf"), 0.0], [0.0, 1.0]])


def test_fit_affine_rejects_non_finite_samples():
    with pytest.raises(ConfigError):
        fit_affine([((1.0, 0.0), (float("nan"), 0.0)), ((0.0, 1.0), (0.0, 1.0))])
