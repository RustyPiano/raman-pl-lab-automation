"""Burn check: compare two repeated single-point spectra (pure).

The two acquisitions at a point are a burn check, not an average: if the
relative deviation exceeds the threshold, flag a burn/anomaly. Both spectra are
kept by the workflow.
"""

import math

from lab_auto.errors import ConfigError

_EPS = 1e-12


def _l2(values):
    return math.sqrt(sum(float(v) * float(v) for v in values))


def compare_spectra(a, b, *, metric: str, threshold: float):
    """Compare intensity lists ``a`` and ``b``.

    Returns ``{"deviation": float, "burned": bool}``. ``burned`` is True when the
    deviation strictly exceeds ``threshold``.
    """
    if not a or not b:
        # Two empty (failed) acquisitions would otherwise give deviation 0.0 and
        # silently pass the burn check — surface it instead of hiding a capture failure.
        raise ConfigError("burn check requires non-empty spectra")
    if len(a) != len(b):
        raise ConfigError("spectra lengths differ")
    if metric != "relative_l2":
        raise ConfigError(f"unknown burn metric: {metric!r}")

    diff = [float(x) - float(y) for x, y in zip(a, b)]
    deviation = _l2(diff) / (_l2(a) + _EPS)
    return {"deviation": deviation, "burned": deviation > threshold}
