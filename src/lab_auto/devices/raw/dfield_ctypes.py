import ctypes
import math
from collections.abc import Callable

from lab_auto.devices.raw.native import LoadedLibrary, load_library, maybe_configure as _maybe_configure  # noqa: F401
from lab_auto.devices.dfield_validation import (
    validate_dfield_bin_roi,
    validate_dfield_capture_args,
    validate_dfield_image_size,
)
from lab_auto.errors import ConfigError, DeviceError, WorkflowCancelled


WindowsLong = ctypes.c_int32
REQUIRED_EXPORTS = (
    "a4_open",
    "a4_close",
    "a4_get_detector_size",
    "a4_set_exposure",
    "a4_get_exposure",
    "a4_set_gain",
    "a4_get_gain",
    "a4_set_read_mode",
    "a4_get_read_mode",
    "a4_get_pixel_size",
    "a4_single_capture",
    "a4_set_bin",
    "a4_set_roi",
    "a4_get_bin",
    "a4_get_roi",
    "a4_get_current_temp",
    "a4_get_cooling_temp",
    "a4_set_cooling_temp",
    "a4_get_flip",
    "a4_set_flip",
)


def _is_integer_code(value: int, allowed: tuple[int, ...]) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in allowed


def windows_long_array(size: int):
    return (WindowsLong * size)()


def has_required_exports(lib) -> bool:
    return all(hasattr(lib, name) for name in REQUIRED_EXPORTS)


def configure_signatures(lib) -> None:
    _maybe_configure(lib, "a4_open", [], ctypes.c_bool)
    _maybe_configure(lib, "a4_close", [], None)
    _maybe_configure(lib, "a4_get_exposure", [ctypes.POINTER(ctypes.c_float)], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_exposure", [ctypes.c_float], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_gain", [ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_gain", [ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_detector_size", [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_pixel_size", [ctypes.POINTER(ctypes.c_float)], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_read_mode", [ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_read_mode", [ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_bin", [ctypes.c_int, ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_bin", [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_roi", [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int], ctypes.c_bool)
    _maybe_configure(
        lib,
        "a4_get_roi",
        [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)],
        ctypes.c_bool,
    )
    _maybe_configure(lib, "a4_single_capture", [ctypes.POINTER(WindowsLong), ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_cooling_temp", [ctypes.c_float], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_cooling_temp", [ctypes.POINTER(ctypes.c_float)], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_current_temp", [ctypes.POINTER(ctypes.c_float)], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_flip", [ctypes.c_bool], None)
    _maybe_configure(lib, "a4_get_flip", [ctypes.POINTER(ctypes.c_bool)], None)


class DFieldRawClient:
    SATURATION_THRESHOLD = 65535

    def __init__(self, lib):
        self.lib = lib
        self._open = False

    def _require_ok(self, action: str, ok: bool) -> None:
        if not ok:
            raise DeviceError(f"DField operation failed: {action}")

    def _ensure_open(self) -> None:
        if not self._open:
            self._require_ok("open", self.lib.a4_open())
            self._open = True

    def status(self) -> dict:
        self._ensure_open()
        width = ctypes.c_int()
        height = ctypes.c_int()
        exposure = ctypes.c_float()
        gain = ctypes.c_int()
        read_mode = ctypes.c_int()
        pixel_size = ctypes.c_float()
        self._require_ok("get_detector_size", self.lib.a4_get_detector_size(ctypes.byref(width), ctypes.byref(height)))
        self._require_ok("get_exposure", self.lib.a4_get_exposure(ctypes.byref(exposure)))
        self._require_ok("get_gain", self.lib.a4_get_gain(ctypes.byref(gain)))
        self._require_ok("get_read_mode", self.lib.a4_get_read_mode(ctypes.byref(read_mode)))
        self._require_ok("get_pixel_size", self.lib.a4_get_pixel_size(ctypes.byref(pixel_size)))
        return {
            "open": True,
            "width": width.value,
            "height": height.value,
            "exposure_ms": float(exposure.value),
            "gain_code": int(gain.value),
            "read_mode_code": int(read_mode.value),
            "pixel_size_um": float(pixel_size.value),
        }

    def capture(
        self,
        *,
        read_mode_code: int,
        exposure_ms: float,
        gain_code: int,
        frames: int,
        bin_x: int = 1,
        bin_y: int = 1,
        roi: tuple[int, int, int, int] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> dict:
        if not _is_integer_code(read_mode_code, (0, 1)):
            raise ConfigError("DField read_mode_code must be 0 or 1")
        if not _is_integer_code(gain_code, (0, 1)):
            raise ConfigError("DField gain_code must be 0 or 1")
        validate_dfield_capture_args(
            read_mode="fvb" if read_mode_code == 0 else "image",
            exposure_ms=exposure_ms,
            gain="high" if gain_code == 0 else "low",
            frames=frames,
            bin_x=bin_x,
            bin_y=bin_y,
            roi=roi,
        )
        frame_count = int(frames)
        self._ensure_open()
        width = ctypes.c_int()
        height = ctypes.c_int()
        self._require_ok("get_detector_size", self.lib.a4_get_detector_size(ctypes.byref(width), ctypes.byref(height)))
        validate_dfield_bin_roi(bin_x=bin_x, bin_y=bin_y, roi=roi, detector_width=width.value, detector_height=height.value)
        if read_mode_code == 1 and roi is None:
            validate_dfield_image_size(width=width.value, height=height.value, bin_x=bin_x, bin_y=bin_y)
        self._require_ok("set_exposure", self.lib.a4_set_exposure(ctypes.c_float(exposure_ms)))
        self._require_ok("set_gain", self.lib.a4_set_gain(gain_code))
        self._require_ok("set_read_mode", self.lib.a4_set_read_mode(read_mode_code))
        self._require_ok("set_bin", self.lib.a4_set_bin(int(bin_x), int(bin_y)))
        if read_mode_code == 1:
            selected_roi = roi if roi is not None else (0, width.value - 1, 0, height.value - 1)
            self._require_ok(
                "set_roi",
                self.lib.a4_set_roi(int(selected_roi[0]), int(selected_roi[1]), int(selected_roi[2]), int(selected_roi[3])),
            )
        actual_exposure = ctypes.c_float()
        actual_gain = ctypes.c_int()
        actual_read_mode = ctypes.c_int()
        self._require_ok("get_exposure", self.lib.a4_get_exposure(ctypes.byref(actual_exposure)))
        self._require_ok("get_gain", self.lib.a4_get_gain(ctypes.byref(actual_gain)))
        self._require_ok("get_read_mode", self.lib.a4_get_read_mode(ctypes.byref(actual_read_mode)))
        expected_exposure = ctypes.c_float(exposure_ms).value
        if not math.isclose(actual_exposure.value, expected_exposure, rel_tol=1e-6, abs_tol=1e-3):
            raise DeviceError(
                f"DField exposure readback mismatch (read {actual_exposure.value}, need {expected_exposure})"
            )
        if actual_gain.value != gain_code:
            raise DeviceError(f"DField gain readback mismatch (read {actual_gain.value}, need {gain_code})")
        if actual_read_mode.value != read_mode_code:
            raise DeviceError(
                f"DField read-mode readback mismatch (read {actual_read_mode.value}, need {read_mode_code})"
            )
        bin_x = ctypes.c_int()
        bin_y = ctypes.c_int()
        col_from = ctypes.c_int()
        col_to = ctypes.c_int()
        row_from = ctypes.c_int()
        row_to = ctypes.c_int()
        self._require_ok("get_bin", self.lib.a4_get_bin(ctypes.byref(bin_x), ctypes.byref(bin_y)))
        if read_mode_code == 0:
            capture_width = width.value // max(bin_x.value, 1)
            capture_height = 1
            size = capture_width
            returned_roi = None
        else:
            self._require_ok("get_roi", self.lib.a4_get_roi(ctypes.byref(col_from), ctypes.byref(col_to), ctypes.byref(row_from), ctypes.byref(row_to)))
            has_roi = col_to.value >= col_from.value and row_to.value >= row_from.value
            roi_width = col_to.value - col_from.value + 1 if has_roi else width.value
            roi_height = row_to.value - row_from.value + 1 if has_roi else height.value
            capture_width = roi_width // max(bin_x.value, 1)
            capture_height = roi_height // max(bin_y.value, 1)
            size = capture_width * capture_height
            returned_roi = (col_from.value, col_to.value, row_from.value, row_to.value) if has_roi else None
        if size <= 0:
            raise DeviceError("DField capture size is zero")
        totals = [0 for _ in range(size)]
        saturated = [False for _ in range(size)]
        for _ in range(frame_count):
            if should_cancel is not None and should_cancel():
                raise WorkflowCancelled("DField capture cancelled between frames")
            buffer = windows_long_array(size)
            self._require_ok("single_capture", self.lib.a4_single_capture(buffer, size))
            if should_cancel is not None and should_cancel():
                raise WorkflowCancelled("DField capture cancelled after the active frame")
            for index in range(size):
                value = int(buffer[index])
                totals[index] += value
                saturated[index] = saturated[index] or value >= self.SATURATION_THRESHOLD
        values = [round(total / frame_count) for total in totals]
        return {
            "width": capture_width,
            "height": capture_height,
            "bin_x": bin_x.value,
            "bin_y": bin_y.value,
            "roi": returned_roi,
            "detector_width": width.value,
            "detector_height": height.value,
            "values": values,
            "saturated": saturated,
            "raw_frames_count": frame_count,
            "saturation_threshold": self.SATURATION_THRESHOLD,
        }

    def close(self) -> None:
        if self._open:
            self.lib.a4_close()
            self._open = False

    def temperature_c(self) -> float:
        self._ensure_open()
        temp = ctypes.c_float()
        self._require_ok("get_current_temp", self.lib.a4_get_current_temp(ctypes.byref(temp)))
        return float(temp.value)
