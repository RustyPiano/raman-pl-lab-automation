import math

import pytest

from lab_auto.devices.zolix_spectrometer import ZolixSpectrometer, direct_to_front_bool, front_bool_to_port
from lab_auto.errors import ConfigError, DeviceError


def test_direct_and_front_alias_map_to_true():
    assert direct_to_front_bool("direct") is True
    assert direct_to_front_bool("front") is True


def test_side_maps_to_false():
    assert direct_to_front_bool("side") is False


def test_front_bool_to_port_uses_clean_names():
    assert front_bool_to_port(True) == "direct"
    assert front_bool_to_port(False) == "side"


def test_adapter_calls_raw_client_not_native_symbols():
    raw = FakeZolixRaw()
    spec = ZolixSpectrometer(raw, device_id=7)

    assert spec.set_entrance_port("side") is True

    assert raw.calls == [("set_entrance_port", 7, False), ("get_entrance_port", 7)]


def test_adapter_exposes_phase1_cli_and_workflow_methods():
    raw = FakeZolixRaw()
    spec = ZolixSpectrometer(raw, device_id=7)

    status = spec.status()
    assert status["device_id"] == 7
    assert status["entrance_port"] == "side"
    assert status["exit_port"] == "direct"
    assert status["grating"] == 1
    assert status["current_wavelength_nm"] == 600.0
    assert status["slit_width_um"] == 100
    assert spec.initialize(entrance_port="side", exit_port="direct") is True
    assert spec.set_grating(1) is True
    assert spec.move_to_wavelength_nm(600.0) is True
    assert spec.set_slit_width_um(100) is True
    assert spec.pixels_to_waves(turret=0, grating=1, center_wavelength_nm=600.0, width=2048, count=3, bin_x=1) == [599.99, 600.0, 600.01]
    spec.close()

    assert raw.calls == [
        ("get_status", 7),
        ("get_entrance_port", 7),
        ("get_exit_port", 7),
        ("get_grating", 7),
        ("get_current_wavelength_nm", 7),
        ("get_slit_width_um", 7),
        ("set_entrance_port", 7, False),
        ("get_entrance_port", 7),
        ("set_exit_port", 7, True),
        ("get_exit_port", 7),
        ("set_grating", 7, 1),
        ("get_grating", 7),
        ("move_to_wavelength_nm", 7, 600.0),
        ("get_current_wavelength_nm", 7),
        ("set_slit_width_um", 7, 100),
        ("get_slit_width_um", 7),
        ("pixels_to_waves", 7, 0, 1, 600.0, 2048, 3, 1),
        ("close", 7),
    ]


def test_adapter_wraps_false_result_as_device_error():
    raw = FakeZolixRaw(fail_actions={"set_grating"})
    spec = ZolixSpectrometer(raw, device_id=7)

    with pytest.raises(DeviceError, match="set_grating"):
        spec.set_grating(1)


def test_adapter_rejects_setpoint_readback_mismatch():
    raw = FakeZolixRaw()
    spec = ZolixSpectrometer(raw, device_id=7)

    with pytest.raises(DeviceError, match="grating readback mismatch"):
        spec.set_grating(2)


@pytest.mark.parametrize(
    ("method", "value", "message"),
    [
        ("set_grating", 0, "grating"),
        ("set_grating", math.nan, "grating"),
        ("set_grating", 10**400, "grating"),
        ("move_to_wavelength_nm", -1.0, "wavelength"),
        ("move_to_wavelength_nm", 10**400, "wavelength"),
        ("move_to_wavelength_nm", 1e39, "wavelength"),
        ("move_to_wavelength_nm", 1e-46, "wavelength"),
        ("set_slit_width_um", -5, "slit"),
        ("set_slit_width_um", math.nan, "slit"),
        ("set_slit_width_um", 10**400, "slit"),
    ],
)
def test_adapter_validates_optics_before_raw_sdk_calls(method, value, message):
    raw = FakeZolixRaw()
    spec = ZolixSpectrometer(raw, device_id=7)

    with pytest.raises(ConfigError, match=message):
        getattr(spec, method)(value)

    assert raw.calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"grating": 10**400},
        {"center_wavelength_nm": 1e39},
        {"center_wavelength_nm": 1e-46},
        {"width": 10**400},
        {"count": 0},
        {"bin_x": 0},
    ],
)
def test_pixels_to_waves_validates_abi_arguments_before_raw_call(kwargs):
    raw = FakeZolixRaw()
    spec = ZolixSpectrometer(raw, device_id=7)
    args = {"turret": 0, "grating": 1, "center_wavelength_nm": 600.0, "width": 2048, "count": 3, "bin_x": 1}
    args.update(kwargs)

    with pytest.raises(ConfigError):
        spec.pixels_to_waves(**args)

    assert raw.calls == []


class FakeZolixRaw:
    def __init__(self, fail_actions=None):
        self.calls = []
        self.fail_actions = fail_actions or set()

    def set_entrance_port(self, device_id: int, front: bool) -> bool:
        self.calls.append(("set_entrance_port", device_id, front))
        return "set_entrance_port" not in self.fail_actions

    def set_exit_port(self, device_id: int, front: bool) -> bool:
        self.calls.append(("set_exit_port", device_id, front))
        return "set_exit_port" not in self.fail_actions

    def get_status(self, device_id: int) -> dict:
        self.calls.append(("get_status", device_id))
        return {"device_id": device_id, "dll_version": "fake"}

    def get_entrance_port(self, device_id: int) -> bool:
        self.calls.append(("get_entrance_port", device_id))
        return False

    def get_exit_port(self, device_id: int) -> bool:
        self.calls.append(("get_exit_port", device_id))
        return True

    def get_grating(self, device_id: int) -> int:
        self.calls.append(("get_grating", device_id))
        return 1

    def get_current_wavelength_nm(self, device_id: int) -> float:
        self.calls.append(("get_current_wavelength_nm", device_id))
        return 600.0

    def get_slit_width_um(self, device_id: int) -> int:
        self.calls.append(("get_slit_width_um", device_id))
        return 100

    def set_grating(self, device_id: int, grating: int) -> bool:
        self.calls.append(("set_grating", device_id, grating))
        return "set_grating" not in self.fail_actions

    def move_to_wavelength_nm(self, device_id: int, wavelength_nm: float) -> bool:
        self.calls.append(("move_to_wavelength_nm", device_id, wavelength_nm))
        return "move_to_wavelength_nm" not in self.fail_actions

    def set_slit_width_um(self, device_id: int, width_um: int) -> bool:
        self.calls.append(("set_slit_width_um", device_id, width_um))
        return "set_slit_width_um" not in self.fail_actions

    def pixels_to_waves(self, device_id: int, *, turret: int, grating: int, center_wavelength_nm: float, width: int, count: int, bin_x: int) -> list[float]:
        self.calls.append(("pixels_to_waves", device_id, turret, grating, center_wavelength_nm, width, count, bin_x))
        return [599.99, 600.0, 600.01]

    def close(self, device_id: int) -> None:
        self.calls.append(("close", device_id))
