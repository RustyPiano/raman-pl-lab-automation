import ctypes
import os
from dataclasses import dataclass
from pathlib import Path

from lab_auto.devices.dfield_validation import validate_dfield_bin_roi, validate_dfield_image_size
from lab_auto.errors import ConfigError, DeviceError


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


@dataclass(frozen=True)
class LoadedLibrary:
    lib: object
    dll_directory_handle: object | None = None

    def __getattr__(self, name: str):
        return getattr(self.lib, name)


def windows_long_array(size: int):
    return (WindowsLong * size)()


def load_library(dll_path: Path) -> LoadedLibrary:
    dll_path = Path(dll_path)
    dll_directory_handle = None
    if hasattr(os, "add_dll_directory"):
        dll_directory_handle = os.add_dll_directory(str(dll_path.parent))
    lib = ctypes.WinDLL(str(dll_path)) if hasattr(ctypes, "WinDLL") else ctypes.CDLL(str(dll_path))
    return LoadedLibrary(lib=lib, dll_directory_handle=dll_directory_handle)


def _maybe_configure(lib, name: str, argtypes, restype) -> None:
    func = getattr(lib, name, None)
    if func is not None:
        func.argtypes = argtypes
        func.restype = restype


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
    ) -> dict:
        if read_mode_code not in (0, 1):
            raise ConfigError("DField read_mode_code must be 0 or 1")
        if exposure_ms <= 0:
            raise ConfigError("DField exposure_ms must be positive")
        if gain_code not in (0, 1):
            raise ConfigError("DField gain_code must be 0 or 1")
        if frames < 1:
            raise ConfigError("DField frames must be at least 1")
        if read_mode_code == 0 and roi is not None:
            raise ConfigError("DField ROI is only supported for image read_mode")
        validate_dfield_bin_roi(bin_x=bin_x, bin_y=bin_y, roi=roi)
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
            buffer = windows_long_array(size)
            self._require_ok("single_capture", self.lib.a4_single_capture(buffer, size))
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
