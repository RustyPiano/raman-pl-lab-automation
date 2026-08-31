import csv
from collections.abc import Callable
from pathlib import Path

from lab_auto.devices.dfield_validation import validate_dfield_capture_args
from lab_auto.errors import ConfigError
from lab_auto.workflow.data import CaptureFrame


def gain_to_code(gain: str) -> int:
    if gain == "high":
        return 0
    if gain == "low":
        return 1
    raise ConfigError(f"unsupported DField gain: {gain}")


def read_mode_to_code(read_mode: str) -> int:
    if read_mode == "fvb":
        return 0
    if read_mode == "image":
        return 1
    raise ConfigError(f"unsupported DField read_mode: {read_mode}")


def _gain_from_code(gain_code: int) -> str:
    return {0: "high", 1: "low"}.get(gain_code, f"unknown:{gain_code}")


def _read_mode_from_code(read_mode_code: int) -> str:
    return {0: "fvb", 1: "image"}.get(read_mode_code, f"unknown:{read_mode_code}")


class DFieldCamera:
    def __init__(self, raw):
        self.raw = raw

    def status(self) -> dict:
        status = dict(self.raw.status())
        if "gain_code" in status:
            status["gain"] = _gain_from_code(int(status.pop("gain_code")))
        if "read_mode_code" in status:
            status["read_mode"] = _read_mode_from_code(int(status.pop("read_mode_code")))
        return status

    def capture(
        self,
        *,
        read_mode: str,
        exposure_ms: float,
        gain: str,
        frames: int,
        bin_x: int = 1,
        bin_y: int = 1,
        roi: tuple[int, int, int, int] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> CaptureFrame:
        validate_dfield_capture_args(
            read_mode=read_mode,
            exposure_ms=exposure_ms,
            gain=gain,
            frames=frames,
            bin_x=bin_x,
            bin_y=bin_y,
            roi=roi,
        )
        capture_kwargs = dict(
            read_mode_code=read_mode_to_code(read_mode),
            exposure_ms=exposure_ms,
            gain_code=gain_to_code(gain),
            frames=frames,
            bin_x=bin_x,
            bin_y=bin_y,
            roi=roi,
        )
        if should_cancel is not None:
            capture_kwargs["should_cancel"] = should_cancel
        result = self.raw.capture(**capture_kwargs)
        return CaptureFrame(
            read_mode=read_mode,
            width=result["width"],
            height=result["height"],
            bin_x=result["bin_x"],
            bin_y=result["bin_y"],
            roi=result["roi"],
            exposure_ms=exposure_ms,
            gain=gain,
            values=result["values"],
            saturated_count=sum(1 for value in result["saturated"] if value),
            saturated=result["saturated"],
            metadata={
                "detector_width": result.get("detector_width", result["width"]),
                "detector_height": result.get("detector_height", result["height"]),
                "raw_frames_count": result["raw_frames_count"],
                "saturation_threshold": result["saturation_threshold"],
            },
            raw_frames_count=result["raw_frames_count"],
            saturation_threshold=result["saturation_threshold"],
        )

    def capture_to_csv(
        self,
        *,
        mode: str,
        exposure_ms: float,
        gain: str,
        out: Path,
        bin_x: int = 1,
        bin_y: int = 1,
        roi: tuple[int, int, int, int] | None = None,
    ) -> None:
        frame = self.capture(read_mode=mode, exposure_ms=exposure_ms, gain=gain, frames=1, bin_x=bin_x, bin_y=bin_y, roi=roi)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if mode == "image":
                expected = frame.width * frame.height
                if expected != len(frame.values):
                    raise ConfigError("image capture dimensions do not match value count")
                writer.writerow(["row", "col", "intensity_raw", "saturated"])
                for index, (value, saturated) in enumerate(zip(frame.values, frame.saturated, strict=True)):
                    row, col = divmod(index, frame.width)
                    writer.writerow([row, col, value, str(saturated).lower()])
            else:
                writer.writerow(["pixel_index", "intensity_raw", "saturated"])
                for index, (value, saturated) in enumerate(zip(frame.values, frame.saturated, strict=True)):
                    writer.writerow([index, value, str(saturated).lower()])

    def close(self) -> None:
        self.raw.close()

    def temperature_c(self) -> float:
        return self.raw.temperature_c()
