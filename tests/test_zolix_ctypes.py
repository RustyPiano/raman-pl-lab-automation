import ctypes

from lab_auto.devices.raw.zolix_ctypes import LoadedLibrary, ZolixRawClient, configure_signatures, has_required_exports


class FakeLibrary:
    pass


def function():
    def inner(*args):
        return None

    return inner


def test_configures_spec_get_error_as_void_three_args():
    lib = FakeLibrary()
    lib.spec_get_error = function()

    configure_signatures(lib)

    assert lib.spec_get_error.argtypes == [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    assert lib.spec_get_error.restype is None


def test_configures_port_functions_with_bool():
    lib = FakeLibrary()
    lib.spec_set_entrance_port = function()
    lib.spec_set_exit_port = function()

    configure_signatures(lib)

    assert lib.spec_set_entrance_port.argtypes == [ctypes.c_int, ctypes.c_bool]
    assert lib.spec_set_exit_port.argtypes == [ctypes.c_int, ctypes.c_bool]


def test_configures_usb_mode_as_void_return():
    lib = FakeLibrary()
    lib.spec_set_usb_mode = function()

    configure_signatures(lib)

    assert lib.spec_set_usb_mode.argtypes == [ctypes.c_bool]
    assert lib.spec_set_usb_mode.restype is None


def test_raw_client_applies_usb_mode_before_enumeration():
    lib = FakeLibrary()
    lib.usb_mode_calls = []
    lib.spec_set_usb_mode = lambda enabled: lib.usb_mode_calls.append(enabled)
    raw = ZolixRawClient(lib)

    raw.set_usb_mode(True)

    assert lib.usb_mode_calls == [True]


def test_loaded_library_retains_dll_directory_handle():
    handle = object()
    lib = FakeLibrary()

    loaded = LoadedLibrary(lib=lib, dll_directory_handle=handle)

    assert loaded.dll_directory_handle is handle
    assert loaded.lib is lib


def test_required_exports_include_phase1_operations():
    lib = FakeLibrary()
    for name in (
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
        "spec_get_grating",
        "spec_get_curr_wave",
        "spec_get_entrance_port",
        "spec_get_exit_port",
        "spec_get_slit_width",
    ):
        setattr(lib, name, function())

    assert has_required_exports(lib) is True
    delattr(lib, "spec_set_grating")
    assert has_required_exports(lib) is False
