from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class CaptureFrame:
    read_mode: str
    width: int
    height: int
    bin_x: int
    bin_y: int
    roi: tuple[int, int, int, int] | None
    exposure_ms: float
    gain: str
    values: list[int]
    saturated_count: int
    saturated: list[bool]
    metadata: dict[str, Any]
    raw_frames_count: int = 1
    saturation_threshold: int = 65535


@dataclass(frozen=True)
class SpectrumData:
    x_axis_type: str
    x: list[float | int]
    intensity_raw: list[float]
    intensity_background: list[float] | None
    intensity_corrected: list[float] | None
    saturated: list[bool]
    metadata: dict[str, Any]
    background_saturated: list[bool] | None = None

    def with_background(
        self,
        background: list[float],
        corrected: list[float],
        background_saturated: list[bool],
    ) -> "SpectrumData":
        return replace(
            self,
            intensity_background=list(background),
            intensity_corrected=list(corrected),
            background_saturated=list(background_saturated),
        )
