"""Tests for the rewritten device/light endpoints (routers/devices.py).

These exercise the router in isolation (a bare FastAPI app with only
``devices.router`` mounted, no lifespan) via TestClient, with
``DeviceFactory``/``task_queue`` monkeypatched to fakes -- real serial ports
are never touched.
"""
import copy

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lab_auto.api.routers import devices
from lab_auto.errors import DeviceError

# Mirrors tests/test_light_config.py's fixture: a minimal valid devices.yaml.
BASE = {
    "runtime": {"mode": "dry_run", "log_level": "info"},
    "stage": {
        "type": "waynelabs_linear",
        "port": "COM5",
        "baudrate": 9600,
        "resolution_um": {"x": 0.04, "y": 0.04, "z": 0.04},
        "default_speed": 8,
        "soft_limits_um": {"x": [-5000, 5000], "y": [-5000, 5000], "z": [-1000, 1000]},
        "state_file": "state/stage_position.json",
        "max_unknown_move_um": 100,
    },
    "spectrometer": {"type": "zolix", "dll_path": "C:/x.dll", "usb_mode": True},
    "camera": {"type": "dfield_vs_a4", "dll_path": "C:/y.dll"},
    "light": {"type": "manual", "manual_light_control": True},
}

PWM_LIGHT = {
    "type": "pwm_modbus",
    "manual_light_control": False,
    "port": "COM7",
    "station_id": 1,
    "baudrate": 9600,
    "max_output_voltage_v": 5.0,
    "required_output_voltage_v": 5.0,
    "channels": {
        "led": {"channel": 1, "frequency_hz": 1000, "duty_percent": 5.0, "default_off_required": True},
        "laser": {"channel": 2, "frequency_hz": 1000, "duty_percent": 5.0, "default_off_required": True},
    },
}


def _write(tmp_path, light):
    data = copy.deepcopy(BASE)
    data["light"] = copy.deepcopy(light)
    path = tmp_path / "devices.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return str(path)


class FakeQueue:
    """Stand-in for the task_queue singleton: controllable busy flag."""

    def __init__(self, *, busy=False, cancelled=None, active_light=False):
        self._busy = busy
        self._cancelled = cancelled if cancelled is not None else ["job-1"]
        self._active_light = active_light
        self.cancel_all_called = False

    def is_hardware_busy(self):
        return self._busy

    async def cancel_all(self):
        self.cancel_all_called = True
        return self._cancelled

    def safety_devices_path(self):
        return None

    def force_active_light_off(self):
        return self._active_light


class FakeLight:
    """Records every call made to it; never touches real hardware."""

    def __init__(self, *, fail_reset=False):
        self.calls = []
        self.fail_reset = fail_reset

    def read_hardware_state(self):
        self.calls.append(("read_hardware_state",))
        return {
            "voltage_register": 50,
            "channel_states": {1: 0, 2: 0, 3: 0, 4: 0, 5: 0},
            "laser_state": "off_confirmed",
            "led_state": "off_confirmed",
        }

    def safety_reset(self):
        self.calls.append(("safety_reset",))
        if self.fail_reset:
            raise DeviceError("channel 2 stuck on")

    def close(self, *, all_off=True):
        self.calls.append(("close", all_off))


def _fake_factory_class(light, create_light_calls):
    """A DeviceFactory stand-in: create_light(...) returns the given fake light
    and records the ``initial_all_off`` kwarg it was called with."""

    class FakeFactory:
        def create_light(self, config, *, initial_all_off=True):
            create_light_calls.append(initial_all_off)
            return light

        def run_status(self, config):
            return {"runtime_mode": "dry_run", "scan": {"fake": "scan"}, "doctor": {"fake": "doctor"}}

        def run_scan(self, config):
            return {"runtime_mode": "dry_run", "fake": "scan-result"}

    return FakeFactory


@pytest.fixture
def app_client():
    app = FastAPI()
    app.include_router(devices.router)
    return TestClient(app)


# --- POST /light/on removed ---------------------------------------------------

def test_light_on_endpoint_is_removed(app_client):
    response = app_client.post("/api/devices/light/on")
    assert response.status_code == 404


# --- GET /light/status ---------------------------------------------------------

def test_light_status_idle_reads_without_writing_channels(app_client, tmp_path, monkeypatch):
    config_path = _write(tmp_path, PWM_LIGHT)
    light = FakeLight()
    create_light_calls = []
    monkeypatch.setattr(devices, "DeviceFactory", _fake_factory_class(light, create_light_calls))
    monkeypatch.setattr(devices, "task_queue", FakeQueue(busy=False))
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.get("/api/devices/light/status")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "pwm_modbus"
    assert body["hardware_state"]["laser_state"] == "off_confirmed"
    assert body["hardware_state"]["channel_states"] == {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    # Status is read-only: created with initial_all_off=False and closed the
    # same way -- no channel write anywhere in this path.
    assert create_light_calls == [False]
    assert light.calls == [("read_hardware_state",), ("close", False)]


def test_light_status_busy_returns_409(app_client, tmp_path, monkeypatch):
    config_path = _write(tmp_path, PWM_LIGHT)
    monkeypatch.setattr(devices, "task_queue", FakeQueue(busy=True))
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.get("/api/devices/light/status")

    assert response.status_code == 409


def test_light_status_manual_reports_software_state_even_if_busy(app_client, tmp_path, monkeypatch):
    config_path = _write(tmp_path, BASE["light"])
    # Even a "busy" queue must not block a manual light's status: there is no
    # hardware for this endpoint to race against.
    monkeypatch.setattr(devices, "task_queue", FakeQueue(busy=True))
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.get("/api/devices/light/status")

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "manual"
    assert body["hardware_state"] is None


# --- POST /light/off ------------------------------------------------------------

def test_light_off_idle_calls_safety_reset(app_client, tmp_path, monkeypatch):
    config_path = _write(tmp_path, PWM_LIGHT)
    light = FakeLight()
    create_light_calls = []
    monkeypatch.setattr(devices, "DeviceFactory", _fake_factory_class(light, create_light_calls))
    queue = FakeQueue(busy=False)
    monkeypatch.setattr(devices, "task_queue", queue)
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.post("/api/devices/light/off")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "off"
    assert body["cancelled_jobs"] == []
    assert queue.cancel_all_called is False
    assert create_light_calls == [False]
    assert ("safety_reset",) in light.calls
    assert ("close", False) in light.calls


def test_light_off_busy_cancels_running_jobs_first(app_client, tmp_path, monkeypatch):
    config_path = _write(tmp_path, PWM_LIGHT)
    light = FakeLight()
    create_light_calls = []
    monkeypatch.setattr(devices, "DeviceFactory", _fake_factory_class(light, create_light_calls))
    queue = FakeQueue(busy=True, cancelled=["job-a", "job-b"])
    monkeypatch.setattr(devices, "task_queue", queue)
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.post("/api/devices/light/off")

    assert response.status_code == 200
    body = response.json()
    assert queue.cancel_all_called is True
    assert body["cancelled_jobs"] == ["job-a", "job-b"]
    # Off is still attempted even though hardware was reported busy.
    assert ("safety_reset",) in light.calls


def test_light_off_busy_uses_active_handle_even_if_config_disappeared(app_client, tmp_path, monkeypatch):
    queue = FakeQueue(busy=True, cancelled=["job-a"], active_light=True)
    monkeypatch.setattr(devices, "task_queue", queue)
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", str(tmp_path / "missing.yaml"))

    response = app_client.post("/api/devices/light/off")

    assert response.status_code == 200
    assert response.json()["status"] == "off"
    assert response.json()["cancelled_jobs"] == ["job-a"]


def test_light_off_manual_returns_manual_status(app_client, tmp_path, monkeypatch):
    config_path = _write(tmp_path, BASE["light"])
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.post("/api/devices/light/off")

    assert response.status_code == 200
    assert response.json()["status"] == "manual"


def test_light_off_surfaces_safety_reset_failure_as_400(app_client, tmp_path, monkeypatch):
    config_path = _write(tmp_path, PWM_LIGHT)
    light = FakeLight(fail_reset=True)
    create_light_calls = []
    monkeypatch.setattr(devices, "DeviceFactory", _fake_factory_class(light, create_light_calls))
    monkeypatch.setattr(devices, "task_queue", FakeQueue(busy=False))
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.post("/api/devices/light/off")

    assert response.status_code == 400
    assert "channel 2" in response.json()["detail"]


# --- GET /status, POST /scan: busy check + thread pool execution ---------------

def test_devices_status_busy_returns_409(app_client, monkeypatch):
    monkeypatch.setattr(devices, "task_queue", FakeQueue(busy=True))

    response = app_client.get("/api/devices/status")

    assert response.status_code == 409


def test_devices_scan_busy_returns_409(app_client, monkeypatch):
    monkeypatch.setattr(devices, "task_queue", FakeQueue(busy=True))

    response = app_client.post("/api/devices/scan")

    assert response.status_code == 409


def test_devices_status_idle_runs_and_returns_scan_result(app_client, tmp_path, monkeypatch):
    config_path = _write(tmp_path, BASE["light"])
    monkeypatch.setattr(devices, "task_queue", FakeQueue(busy=False))
    monkeypatch.setattr(devices, "DeviceFactory", _fake_factory_class(FakeLight(), []))
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.get("/api/devices/status")

    assert response.status_code == 200
    body = response.json()
    assert body["scan"] == {"fake": "scan"}
    assert body["doctor"] == {"fake": "doctor"}


def test_devices_scan_idle_runs_and_returns_scan_result(app_client, tmp_path, monkeypatch):
    config_path = _write(tmp_path, BASE["light"])
    monkeypatch.setattr(devices, "task_queue", FakeQueue(busy=False))
    monkeypatch.setattr(devices, "DeviceFactory", _fake_factory_class(FakeLight(), []))
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.post("/api/devices/scan")

    assert response.status_code == 200
    assert response.json()["fake"] == "scan-result"
