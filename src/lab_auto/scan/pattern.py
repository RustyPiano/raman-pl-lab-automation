"""Per-center measurement points (pure).

For a detected sample center, produce the center point plus ``surrounding_count``
parameterized surrounding points at the configured distance and angles. Each
point is later measured ``repeats_per_point`` times for a burn check.
"""

import math

from lab_auto.config import ScanPattern


def measurement_points(center_xy_um, pattern: ScanPattern):
    """Ordered ``[(x_um, y_um, role)]``: center first, then surrounding points."""
    cx, cy = float(center_xy_um[0]), float(center_xy_um[1])
    points = [(cx, cy, "center")]
    for i, angle_deg in enumerate(pattern.surrounding_angles_deg):
        theta = math.radians(float(angle_deg))
        x = cx + pattern.surrounding_distance_um * math.cos(theta)
        y = cy + pattern.surrounding_distance_um * math.sin(theta)
        points.append((x, y, f"surrounding_{i}"))
    return points
