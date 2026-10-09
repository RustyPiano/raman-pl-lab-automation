"""Burn check: compare two repeated single-point spectra (pure).

The two acquisitions at a point are a burn check, not an average: if the
relative deviation exceeds the threshold, flag a burn/anomaly. Both spectra are
kept by the workflow.
"""

import math

from lab_auto.errors import ConfigError

_EPS = 1e-12


def _l2(values):
    return math.hypot(*values)


def compare_spectra(a, b, *, threshold: float):
    """Compare intensity lists ``a`` and ``b`` by relative L2 deviation.

    Returns ``{"deviation": float, "burned": bool}``. ``burned`` is True when the
    deviation strictly exceeds ``threshold``.
    """
    if not a or not b:
        # Two empty (failed) acquisitions would otherwise give deviation 0.0 and
        # silently pass the burn check — surface it instead of hiding a capture failure.
        raise ConfigError("burn check requires non-empty spectra")
    if len(a) != len(b):
        raise ConfigError("spectra lengths differ")
    a, b = [float(x) for x in a], [float(x) for x in b]
    if not all(math.isfinite(x) for x in [*a, *b]):
        raise ConfigError("burn check requires finite spectra")
    reference = _l2(a)
    if reference <= _EPS or not math.isfinite(reference):
        raise ConfigError("burn check reference signal is zero or invalid; cannot classify")

    diff = [x - y for x, y in zip(a, b)]
    deviation = _l2(diff) / reference
    if not math.isfinite(deviation):
        raise ConfigError("burn deviation is not finite; cannot classify")
    return {"deviation": deviation, "burned": deviation > threshold}
