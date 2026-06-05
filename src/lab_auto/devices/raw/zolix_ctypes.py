import ctypes
import os
from dataclasses import dataclass
from pathlib import Path

from lab_auto.errors import DeviceError


REQUIRED_EXPORTS = (
    "spec_get_dll_ver",
    "spec_set_usb_mode",
    "spec_enum_dev_count",
    "spec_enum_dev_sn",
    "spec_open",
    "spec_close",
    "spec_set_entrance_port",
    "spec_set_exit_port",
    "spec_set_grating",
    "spec_move_to_wave",
    "spec_set_slit_width",
    "spec_pixels_to_waves",
    "spec_get_entrance_port",
    "spec_get_exit_port",
    "spec_get_grating",
    "spec_get_curr_wave",
    "spec_get_slit_width",
)


@dataclass(frozen=True)
class LoadedLibrary:
    lib: object
    dll_directory_handle: object | None = None

    def __getattr__(self, name: str):
        return getattr(self.lib, name)


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
    _maybe_configure(lib, "spec_get_dll_ver", [ctypes.c_char_p, ctypes.c_int], None)
    _maybe_configure(lib, "spec_set_usb_mode", [ctypes.c_bool], None)
    _maybe_configure(lib, "spec_enum_dev_count", [], ctypes.c_int)
    _maybe_configure(lib, "spec_enum_dev_sn", [ctypes.c_int, ctypes.c_char_p, ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "spec_open", [ctypes.c_char_p], ctypes.c_int)
    _maybe_configure(lib, "spec_close", [ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_is_open", [ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_error", [ctypes.c_int, ctypes.c_char_p, ctypes.c_int], None)
    _maybe_configure(lib, "spec_set_grating", [ctypes.c_int, ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_grating", [ctypes.c_int, ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "spec_move_to_wave", [ctypes.c_int, ctypes.c_float], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_curr_wave", [ctypes.c_int, ctypes.POINTER(ctypes.c_float)], ctypes.c_bool)
    _maybe_configure(lib, "spec_set_entrance_port", [ctypes.c_int, ctypes.c_bool], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_entrance_port", [ctypes.c_int, ctypes.POINTER(ctypes.c_bool)], ctypes.c_bool)
    _maybe_configure(lib, "spec_set_exit_port", [ctypes.c_int, ctypes.c_bool], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_exit_port", [ctypes.c_int, ctypes.POINTER(ctypes.c_bool)], ctypes.c_bool)
    _maybe_configure(lib, "spec_set_slit_width", [ctypes.c_int, ctypes.c_int, ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_slit_width", [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(
        lib,
        "spec_pixels_to_waves",
        [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_float)],
        ctypes.c_bool,
    )


class ZolixRawClient:
    def __init__(self, lib):
        self.lib = lib

    def set_usb_mode(self, enabled: bool) -> None:
        self.lib.spec_set_usb_mode(bool(enabled))

    def enumerate_serial_numbers(self) -> list[str]:
        count = int(self.lib.spec_enum_dev_count())
        serials: list[str] = []
        for index in range(max(count, 0)):
            serial_number = ctypes.create_string_buffer(128)
            if self.lib.spec_enum_dev_sn(index, serial_number, len(serial_number)):
                serials.append(serial_number.value.decode(errors="replace"))
        return serials

    def open_first_device(self) -> int:
        serials = self.enumerate_serial_numbers()
        if not serials:
            raise DeviceError("no Zolix spectrometer found")
        device_id = int(self.lib.spec_open(serials[0].encode()))
        if device_id < 0:
            raise DeviceError("failed to open Zolix spectrometer")
        return device_id

    def get_status(self, device_id: int) -> dict:
        version = ctypes.create_string_buffer(128)
        if hasattr(self.lib, "spec_get_dll_ver"):
            self.lib.spec_get_dll_ver(version, len(version))
        return {"device_id": device_id, "dll_version": version.value.decode(errors="replace")}

    def get_entrance_port(self, device_id: int) -> bool:
        front = ctypes.c_bool()
        if not self.lib.spec_get_entrance_port(device_id, ctypes.byref(front)):
            raise DeviceError("failed to read Zolix entrance port")
        return bool(front.value)

    def get_exit_port(self, device_id: int) -> bool:
        front = ctypes.c_bool()
        if not self.lib.spec_get_exit_port(device_id, ctypes.byref(front)):
            raise DeviceError("failed to read Zolix exit port")
        return bool(front.value)

    def get_grating(self, device_id: int) -> int:
        grating = ctypes.c_int()
        if not self.lib.spec_get_grating(device_id, ctypes.byref(grating)):
            raise DeviceError("failed to read Zolix grating")
        return int(grating.value)

    def get_current_wavelength_nm(self, device_id: int) -> float:
        wave = ctypes.c_float()
        if not self.lib.spec_get_curr_wave(device_id, ctypes.byref(wave)):
            raise DeviceError("failed to read Zolix current wavelength")
        return float(wave.value)

    def get_slit_width_um(self, device_id: int) -> int:
        width = ctypes.c_int()
        if not self.lib.spec_get_slit_width(device_id, 0, ctypes.byref(width)):
            raise DeviceError("failed to read Zolix slit width")
        return int(width.value)

    def set_entrance_port(self, device_id: int, front: bool) -> bool:
        return bool(self.lib.spec_set_entrance_port(device_id, front))

    def set_exit_port(self, device_id: int, front: bool) -> bool:
        return bool(self.lib.spec_set_exit_port(device_id, front))

    def set_grating(self, device_id: int, grating: int) -> bool:
        return bool(self.lib.spec_set_grating(device_id, grating))

    def move_to_wavelength_nm(self, device_id: int, wavelength_nm: float) -> bool:
        return bool(self.lib.spec_move_to_wave(device_id, ctypes.c_float(wavelength_nm)))

    def set_slit_width_um(self, device_id: int, width_um: int) -> bool:
        return bool(self.lib.spec_set_slit_width(device_id, 0, width_um))

    def pixels_to_waves(
        self,
        device_id: int,
        *,
        turret: int,
        grating: int,
        center_wavelength_nm: float,
        width: int,
        count: int,
        bin_x: int,
    ) -> list[float]:
        values = (ctypes.c_float * count)()
        ok = self.lib.spec_pixels_to_waves(device_id, turret, grating, ctypes.c_float(center_wavelength_nm), width, count, bin_x, values)
        if not ok:
            return []
        return [float(values[index]) for index in range(count)]

    def close(self, device_id: int) -> None:
        self.lib.spec_close(device_id)
