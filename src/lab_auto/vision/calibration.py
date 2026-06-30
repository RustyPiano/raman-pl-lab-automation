"""Affine pixel->stage calibration (pure 2x2 linear algebra).

The image center is the origin. A detected sample at pixel ``p`` must shift to
the image center ``c`` (= laser spot), an image shift of ``(c - p)`` pixels.
A stage move ``S`` (um) shifts the imaged feature by ``P = B*S`` pixels, so the
move producing shift ``(c - p)`` is ``S = A*(c - p)`` with ``A = B^-1``
(um-per-pixel). ``A`` captures scale, rotation, anisotropy and axis sign.
"""

import math

from lab_auto.config import Calibration
from lab_auto.errors import ConfigError


def mat_inverse_2x2(m):
    """Inverse of a 2x2 matrix (list/tuple of two 2-rows). Singular -> ConfigError."""
    (a, b), (c, d) = m[0], m[1]
    det = a * d - b * c
    # Reject exact AND near-singular (relative to matrix scale): a tiny determinant
    # blows up um/pixel coefficients and would drive the stage/laser wildly off.
    scale = max(abs(a), abs(b), abs(c), abs(d), 1.0)
    if not math.isfinite(det) or abs(det) <= 1e-12 * scale * scale:
        raise ConfigError("calibration matrix is singular or near-singular (non-invertible)")
    inv_det = 1.0 / det
    return [
        [d * inv_det, -b * inv_det],
        [-c * inv_det, a * inv_det],
    ]


def _matmul_2x2(p, q):
    return [
        [p[0][0] * q[0][0] + p[0][1] * q[1][0], p[0][0] * q[0][1] + p[0][1] * q[1][1]],
        [p[1][0] * q[0][0] + p[1][1] * q[1][0], p[1][0] * q[0][1] + p[1][1] * q[1][1]],
    ]


def fit_affine(samples):
    """Fit the um-per-pixel matrix ``A`` from calibration samples.

    ``samples = [(stage_delta_um, pixel_delta), ...]`` where ``pixel_delta`` is
    the observed feature pixel shift for the commanded ``stage_delta_um``.
    Fits ``B`` (pixels-per-um) via least squares
    ``B = (sum P_i S_i^T)(sum S_i S_i^T)^-1`` then returns ``A = B^-1``.
    Requires >= 2 linearly-independent stage moves; otherwise ``ConfigError``.
    """
    if len(samples) < 2:
        raise ConfigError("affine fit needs at least 2 calibration samples")

    # Accumulate normal-equation matrices: PS = sum P_i S_i^T, SS = sum S_i S_i^T.
    ps = [[0.0, 0.0], [0.0, 0.0]]
    ss = [[0.0, 0.0], [0.0, 0.0]]
    for stage_delta, pixel_delta in samples:
        sx, sy = float(stage_delta[0]), float(stage_delta[1])
        px, py = float(pixel_delta[0]), float(pixel_delta[1])
        if not all(math.isfinite(v) for v in (sx, sy, px, py)):
            raise ConfigError("calibration samples must be finite")
        ps[0][0] += px * sx
        ps[0][1] += px * sy
        ps[1][0] += py * sx
        ps[1][1] += py * sy
        ss[0][0] += sx * sx
        ss[0][1] += sx * sy
        ss[1][0] += sy * sx
        ss[1][1] += sy * sy

    ss_inv = mat_inverse_2x2(ss)  # ConfigError if stage moves are colinear
    b = _matmul_2x2(ps, ss_inv)
    return mat_inverse_2x2(b)  # A = B^-1


def pixel_to_stage_delta(calib: Calibration, pixel):
    """Relative stage move (dx_um, dy_um) to bring ``pixel`` under the laser.

    ``A @ (image_center - pixel)``.
    """
    ex = calib.image_center_px - float(pixel[0])
    ey = calib.image_center_py - float(pixel[1])
    dx = calib.a11 * ex + calib.a12 * ey
    dy = calib.a21 * ex + calib.a22 * ey
    return (dx, dy)
