"""Per-center measurement points (pure).

For a detected sample center, produce the center point plus ``surrounding_count``
parameterized surrounding points at the configured distance and angles. Each
point is later measured ``repeats_per_point`` times for a burn check.
"""

import math

from lab_auto.config import ScanPattern
from lab_auto.errors import ConfigError


def measurement_points(center_xy_um, pattern: ScanPattern):
    """Ordered ``[(x_um, y_um, role)]``: center first, then surrounding points."""
    if pattern.repeats_per_point < 2:
        raise ConfigError("repeats_per_point must be >= 2 for a burn check")
    if pattern.surrounding_count != len(pattern.surrounding_angles_deg):
        raise ConfigError("surrounding_count must equal len(surrounding_angles_deg)")
    if pattern.surrounding_count > 0 and pattern.surrounding_distance_um <= 0:
        raise ConfigError("surrounding_distance_um must be positive")

    cx, cy = float(center_xy_um[0]), float(center_xy_um[1])
    points = [(cx, cy, "center")]
    for i, angle_deg in enumerate(pattern.surrounding_angles_deg):
        theta = math.radians(float(angle_deg))
        x = cx + pattern.surrounding_distance_um * math.cos(theta)
        y = cy + pattern.surrounding_distance_um * math.sin(theta)
        points.append((x, y, f"surrounding_{i}"))
    return points
