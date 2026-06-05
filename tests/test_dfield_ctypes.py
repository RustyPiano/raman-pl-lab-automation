import ctypes
import pytest

from lab_auto.devices.raw.dfield_ctypes import DFieldRawClient, LoadedLibrary, configure_signatures, has_required_exports, windows_long_array
from lab_auto.errors import ConfigError


class FakeLibrary:
    pass


def function():
    def inner(*args):
        return True

    return inner


def test_configures_close_as_void():
    lib = FakeLibrary()
    lib.a4_close = function()

    configure_signatures(lib)

    assert lib.a4_close.argtypes == []
    assert lib.a4_close.restype is None


def test_configures_temperature_and_flip_exports():
    lib = FakeLibrary()
    lib.a4_get_current_temp = function()
    lib.a4_get_cooling_temp = function()
    lib.a4_set_cooling_temp = function()
    lib.a4_get_flip = function()
    lib.a4_set_flip = function()

    configure_signatures(lib)

    assert lib.a4_get_current_temp.argtypes == [ctypes.POINTER(ctypes.c_float)]
    assert lib.a4_get_current_temp.restype is ctypes.c_bool
    assert lib.a4_get_flip.argtypes == [ctypes.POINTER(ctypes.c_bool)]
    assert lib.a4_set_flip.argtypes == [ctypes.c_bool]


def test_configures_status_readback_exports():
    lib = FakeLibrary()
    lib.a4_get_exposure = function()
    lib.a4_get_gain = function()
    lib.a4_get_read_mode = function()
    lib.a4_get_pixel_size = function()

    configure_signatures(lib)

    assert lib.a4_get_exposure.argtypes == [ctypes.POINTER(ctypes.c_float)]
    assert lib.a4_get_gain.argtypes == [ctypes.POINTER(ctypes.c_int)]
    assert lib.a4_get_read_mode.argtypes == [ctypes.POINTER(ctypes.c_int)]
    assert lib.a4_get_pixel_size.argtypes == [ctypes.POINTER(ctypes.c_float)]


def test_configures_set_bin_and_roi_exports():
    lib = FakeLibrary()
    lib.a4_set_bin = function()
    lib.a4_set_roi = function()

    configure_signatures(lib)

    assert lib.a4_set_bin.argtypes == [ctypes.c_int, ctypes.c_int]
    assert lib.a4_set_roi.argtypes == [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]


def test_capture_uses_windows_32bit_long_buffer():
    arr = windows_long_array(3)

    assert ctypes.sizeof(arr._type_) == 4


def test_loaded_library_retains_dll_directory_handle():
    handle = object()
    lib = FakeLibrary()

    loaded = LoadedLibrary(lib=lib, dll_directory_handle=handle)

    assert loaded.dll_directory_handle is handle
    assert loaded.lib is lib


def test_raw_capture_uses_inclusive_roi_size_and_opens_once():
    lib = FakeDFieldLibrary()
    raw = DFieldRawClient(lib)

    first = raw.capture(read_mode_code=1, exposure_ms=1000, gain_code=1, frames=1)
    second = raw.capture(read_mode_code=1, exposure_ms=1000, gain_code=1, frames=1)

    assert lib.open_calls == 1
    assert lib.capture_sizes == [6, 6]
    assert first["roi"] == (2, 4, 10, 11)
    assert first["width"] == 3
    assert first["height"] == 2
    assert first["values"] == [100, 101, 102, 103, 104, 105]
    assert second["raw_frames_count"] == 1


def test_raw_capture_sets_requested_bin_and_roi_before_capture():
    lib = FakeDFieldLibrary()
    raw = DFieldRawClient(lib)

    raw.capture(read_mode_code=1, exposure_ms=100, gain_code=1, frames=1, bin_x=2, bin_y=3, roi=(1, 4, 3, 6))

    assert lib.set_bin_calls == [(2, 3)]
    assert lib.set_roi_calls == [(1, 4, 3, 6)]


@pytest.mark.parametrize("kwargs", [{"bin_x": 0}, {"bin_x": 65}, {"bin_y": 0}, {"bin_y": 130}, {"roi": (2, 1, 0, 3)}])
def test_raw_capture_validates_bin_and_roi_before_sdk_calls(kwargs):
    lib = FakeDFieldLibrary()
    raw = DFieldRawClient(lib)

    with pytest.raises(ConfigError):
        raw.capture(read_mode_code=1, exposure_ms=100, gain_code=1, frames=1, **kwargs)

    assert lib.set_bin_calls == []
    assert lib.set_roi_calls == []


def test_raw_capture_validates_detector_bound_roi_before_state_mutation():
    lib = FakeDFieldLibrary()
    raw = DFieldRawClient(lib)

    with pytest.raises(ConfigError, match="ROI"):
        raw.capture(read_mode_code=1, exposure_ms=100, gain_code=1, frames=1, roi=(0, 999999, 0, 1))

    assert lib.set_exposure_calls == []
    assert lib.set_gain_calls == []
    assert lib.set_read_mode_calls == []
    assert lib.set_bin_calls == []
    assert lib.set_roi_calls == []


def test_raw_capture_validates_positive_binned_roi_size_before_state_mutation():
    lib = FakeDFieldLibrary()
    raw = DFieldRawClient(lib)

    with pytest.raises(ConfigError, match="size"):
        raw.capture(read_mode_code=1, exposure_ms=100, gain_code=1, frames=1, bin_x=64, roi=(0, 0, 0, 0))

    assert lib.set_exposure_calls == []
    assert lib.set_gain_calls == []
    assert lib.set_read_mode_calls == []
    assert lib.set_bin_calls == []
    assert lib.set_roi_calls == []


def test_raw_capture_validates_full_frame_image_binned_size_before_state_mutation():
    lib = FakeTinyDFieldLibrary()
    raw = DFieldRawClient(lib)

    with pytest.raises(ConfigError, match="size"):
        raw.capture(read_mode_code=1, exposure_ms=100, gain_code=1, frames=1, bin_x=64)

    assert lib.set_exposure_calls == []
    assert lib.set_gain_calls == []
    assert lib.set_read_mode_calls == []
    assert lib.set_bin_calls == []
    assert lib.set_roi_calls == []


def test_raw_fvb_capture_rejects_roi_before_state_mutation():
    lib = FakeDFieldLibrary()
    raw = DFieldRawClient(lib)

    with pytest.raises(ConfigError, match="ROI"):
        raw.capture(read_mode_code=0, exposure_ms=100, gain_code=1, frames=1, roi=(0, 1, 0, 0))

    assert lib.set_exposure_calls == []
    assert lib.set_gain_calls == []
    assert lib.set_read_mode_calls == []
    assert lib.set_bin_calls == []
    assert lib.set_roi_calls == []


def test_raw_fvb_capture_returns_no_stale_roi_metadata():
    lib = FakeDFieldLibrary()
    raw = DFieldRawClient(lib)

    frame = raw.capture(read_mode_code=0, exposure_ms=100, gain_code=1, frames=1)

    assert frame["roi"] is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"exposure_ms": 0},
        {"gain_code": -1},
        {"gain_code": 2},
        {"read_mode_code": 2},
        {"frames": 0},
    ],
)
def test_raw_capture_validates_acquisition_before_open_or_state_mutation(kwargs):
    lib = FakeDFieldLibrary()
    raw = DFieldRawClient(lib)
    args = {"read_mode_code": 1, "exposure_ms": 100, "gain_code": 1, "frames": 1}
    args.update(kwargs)

    with pytest.raises(ConfigError):
        raw.capture(**args)

    assert lib.open_calls == 0
    assert lib.set_exposure_calls == []
    assert lib.set_gain_calls == []
    assert lib.set_read_mode_calls == []


def test_raw_capture_keeps_detector_dimensions_when_binned():
    lib = FakeBinnedDFieldLibrary()
    raw = DFieldRawClient(lib)

    frame = raw.capture(read_mode_code=1, exposure_ms=100, gain_code=1, frames=1)

    assert lib.capture_sizes == [4]
    assert frame["width"] == 2
    assert frame["height"] == 2
    assert frame["detector_width"] == 4
    assert frame["detector_height"] == 4


def test_required_exports_include_phase1_capture_operations():
    lib = FakeLibrary()
    for name in (
        "a4_open",
        "a4_close",
        "a4_get_detector_size",
        "a4_set_exposure",
        "a4_set_gain",
        "a4_set_read_mode",
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
        "a4_get_exposure",
        "a4_get_gain",
        "a4_get_read_mode",
        "a4_get_pixel_size",
    ):
        setattr(lib, name, function())

    assert has_required_exports(lib) is True
    delattr(lib, "a4_get_gain")
    assert has_required_exports(lib) is False
    setattr(lib, "a4_get_gain", function())
    delattr(lib, "a4_get_roi")
    assert has_required_exports(lib) is False


def test_raw_current_temperature_reads_float():
    lib = FakeTemperatureLibrary()
    raw = DFieldRawClient(lib)

    assert raw.temperature_c() == 23.5


def test_raw_status_includes_camera_readbacks():
    lib = FakeStatusLibrary()
    raw = DFieldRawClient(lib)

    assert raw.status() == {
        "open": True,
        "width": 2048,
        "height": 2048,
        "exposure_ms": 1000.0,
        "gain_code": 1,
        "read_mode_code": 0,
        "pixel_size_um": 13.5,
    }


class FakeDFieldLibrary:
    def __init__(self):
        self.open_calls = 0
        self.capture_sizes = []
        self.set_exposure_calls = []
        self.set_gain_calls = []
        self.set_read_mode_calls = []
        self.set_bin_calls = []
        self.set_roi_calls = []

    def a4_open(self):
        self.open_calls += 1
        return True

    def a4_set_exposure(self, exposure):
        self.set_exposure_calls.append(exposure)
        return True

    def a4_set_gain(self, gain):
        self.set_gain_calls.append(gain)
        return True

    def a4_set_read_mode(self, read_mode):
        self.set_read_mode_calls.append(read_mode)
        return True

    def a4_get_detector_size(self, width, height):
        width._obj.value = 2048
        height._obj.value = 2048
        return True

    def a4_get_bin(self, bin_x, bin_y):
        bin_x._obj.value = 1
        bin_y._obj.value = 1
        return True

    def a4_set_bin(self, bin_x, bin_y):
        self.set_bin_calls.append((bin_x, bin_y))
        return True

    def a4_get_roi(self, col_from, col_to, row_from, row_to):
        col_from._obj.value = 2
        col_to._obj.value = 4
        row_from._obj.value = 10
        row_to._obj.value = 11
        return True

    def a4_set_roi(self, col_from, col_to, row_from, row_to):
        self.set_roi_calls.append((col_from, col_to, row_from, row_to))
        return True

    def a4_single_capture(self, buffer, size):
        self.capture_sizes.append(size)
        for index in range(size):
            buffer[index] = 100 + index
        return True

    def a4_close(self):
        return None


class FakeBinnedDFieldLibrary(FakeDFieldLibrary):
    def a4_get_detector_size(self, width, height):
        width._obj.value = 4
        height._obj.value = 4
        return True

    def a4_get_bin(self, bin_x, bin_y):
        bin_x._obj.value = 2
        bin_y._obj.value = 2
        return True

    def a4_get_roi(self, col_from, col_to, row_from, row_to):
        col_from._obj.value = 0
        col_to._obj.value = 3
        row_from._obj.value = 0
        row_to._obj.value = 3
        return True


class FakeTinyDFieldLibrary(FakeDFieldLibrary):
    def a4_get_detector_size(self, width, height):
        width._obj.value = 1
        height._obj.value = 1
        return True


class FakeTemperatureLibrary(FakeDFieldLibrary):
    def a4_get_current_temp(self, temp):
        temp._obj.value = 23.5
        return True


class FakeStatusLibrary(FakeDFieldLibrary):
    def a4_get_exposure(self, exposure):
        exposure._obj.value = 1000.0
        return True

    def a4_get_gain(self, gain):
        gain._obj.value = 1
        return True

    def a4_get_read_mode(self, read_mode):
        read_mode._obj.value = 0
        return True

    def a4_get_pixel_size(self, pixel_size):
        pixel_size._obj.value = 13.5
        return True
