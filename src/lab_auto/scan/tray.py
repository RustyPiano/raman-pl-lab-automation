"""Tray geometry -> wafer-center stage coordinates (pure).

Wafer centers come from the known tray grid (rows/cols/pitch/first-cell
offset/order), not per-wafer detection. Coordinates are home-relative stage
micrometers; ``index`` is the visiting position in the configured order.
"""

from dataclasses import dataclass

from lab_auto.config import TrayLayout


@dataclass(frozen=True)
class WaferCenter:
    x_um: float
    y_um: float
    row: int
    col: int
    index: int


def wafer_centers(layout: TrayLayout):
    """Ordered wafer-center coordinates for the tray grid (layout validated by config)."""
    centers = []
    index = 0
    for row in range(layout.rows):
        col_range = range(layout.cols)
        if layout.order == "serpentine" and row % 2 == 1:
            col_range = reversed(col_range)
        for col in col_range:
            centers.append(
                WaferCenter(
                    x_um=layout.first_cell_offset_x_um + col * layout.pitch_x_um,
                    y_um=layout.first_cell_offset_y_um + row * layout.pitch_y_um,
                    row=row,
                    col=col,
                    index=index,
                )
            )
            index += 1
    return centers
