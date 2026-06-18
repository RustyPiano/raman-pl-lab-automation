"""Burn check: compare two repeated single-point spectra (pure).

The two acquisitions at a point are a burn check, not an average: if the
relative deviation exceeds the threshold, flag a burn/anomaly. Both spectra are
kept by the workflow.
"""

import math

_EPS = 1e-12


def _l2(values):
    return math.sqrt(sum(float(v) * float(v) for v in values))


def compare_spectra(a, b, *, metric: str, threshold: float):
    """Compare intensity lists ``a`` and ``b``.

    Returns ``{"deviation": float, "burned": bool}``. ``burned`` is True when the
    deviation strictly exceeds ``threshold``.
    """
    if len(a) != len(b):
        raise ValueError("spectra lengths differ")
    if metric != "relative_l2":
        raise ValueError(f"unknown burn metric: {metric!r}")

    diff = [float(x) - float(y) for x, y in zip(a, b)]
    deviation = _l2(diff) / (_l2(a) + _EPS)
    return {"deviation": deviation, "burned": deviation > threshold}
