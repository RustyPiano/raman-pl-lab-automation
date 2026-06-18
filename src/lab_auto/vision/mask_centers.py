"""Extract sample centers from a recognition mask.

Pure stdlib: 4-connected components + centroid. No numpy. The recognition code
(冯博士) provides only the mask; we own the center-extraction format.
"""

from dataclasses import dataclass

from lab_auto.errors import ConfigError


@dataclass(frozen=True)
class SampleCenter:
    """Centroid of one connected foreground component in a mask.

    ``pixel_x`` is the mean column, ``pixel_y`` the mean row (both float).
    ``area`` is the pixel count; ``label`` is a stable component id.
    """

    pixel_x: float
    pixel_y: float
    area: int
    label: int


def _validate(mask):
    if not mask:
        return 0, 0
    width = len(mask[0])
    for row in mask:
        if len(row) != width:
            raise ConfigError("mask rows are ragged (unequal length)")
    return len(mask), width


def extract_centers(mask, *, min_area: int = 1):
    """Return one :class:`SampleCenter` per 4-connected foreground component.

    ``mask`` is a 2D ``list[list[int]]`` with 0 = background and any nonzero
    value = foreground. Components smaller than ``min_area`` are dropped.
    Results are sorted deterministically by ``(round(pixel_y), round(pixel_x))``.
    """
    rows, cols = _validate(mask)
    if rows == 0 or cols == 0:
        return []

    visited = [[False] * cols for _ in range(rows)]
    components = []
    next_label = 1

    for sr in range(rows):
        for sc in range(cols):
            if visited[sr][sc] or mask[sr][sc] == 0:
                continue
            # Iterative 4-connected flood fill.
            stack = [(sr, sc)]
            visited[sr][sc] = True
            sum_x = 0
            sum_y = 0
            area = 0
            while stack:
                r, c = stack.pop()
                sum_x += c
                sum_y += r
                area += 1
                for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                    if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc] and mask[nr][nc] != 0:
                        visited[nr][nc] = True
                        stack.append((nr, nc))
            if area >= min_area:
                components.append(
                    SampleCenter(
                        pixel_x=sum_x / area,
                        pixel_y=sum_y / area,
                        area=area,
                        label=next_label,
                    )
                )
                next_label += 1

    components.sort(key=lambda c: (round(c.pixel_y), round(c.pixel_x)))
    # Re-assign labels in deterministic visiting order so ids are stable.
    return [
        SampleCenter(pixel_x=c.pixel_x, pixel_y=c.pixel_y, area=c.area, label=i + 1)
        for i, c in enumerate(components)
    ]
