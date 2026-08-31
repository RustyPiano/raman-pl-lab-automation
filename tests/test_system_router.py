"""Tests for POST /api/emergency-stop (routers/system.py).

Exercises the router in isolation via TestClient with task_queue/DeviceFactory
monkeypatched to fakes -- never touches a real serial port.
"""
import copy

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lab_auto.api.routers import system
from lab_auto.errors import DeviceError

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
    def __init__(self, cancelled, *, active_light=False):
        self._cancelled = cancelled
        self._active_light = active_light
        self.cancel_all_called = False
        self.force_off_called = False

    async def cancel_all(self):
        self.cancel_all_called = True
        return self._cancelled

    def safety_devices_path(self):
        return None

    def force_active_light_off(self):
        self.force_off_called = True
        return self._active_light


class FakeLight:
    def __init__(self, *, fail=False):
        self.calls = []
        self.fail = fail

    def safety_reset(self):
        self.calls.append("safety_reset")
        if self.fail:
            raise DeviceError("stuck channel 2")

    def close(self, *, all_off=True):
        self.calls.append(("close", all_off))


def _fake_factory_class(light):
    class FakeFactory:
        def create_light(self, config, *, initial_all_off=True):
            return light

    return FakeFactory


@pytest.fixture
def app_client():
    app = FastAPI()
    app.include_router(system.router)
    return TestClient(app)


def test_emergency_stop_cancels_jobs_and_confirms_laser_off(tmp_path, monkeypatch, app_client):
    config_path = _write(tmp_path, PWM_LIGHT)
    monkeypatch.setattr(system, "task_queue", FakeQueue(["job-1", "job-2"]))
    light = FakeLight()
    monkeypatch.setattr(system, "DeviceFactory", _fake_factory_class(light))
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.post("/api/emergency-stop")

    assert response.status_code == 200
    body = response.json()
    assert body["jobs_cancelled"] == ["job-1", "job-2"]
    assert body["laser_off"] == "confirmed"
    assert "safety_reset" in light.calls
    assert ("close", False) in light.calls


def test_emergency_stop_reports_failure_honestly_without_500(tmp_path, monkeypatch, app_client):
    config_path = _write(tmp_path, PWM_LIGHT)
    monkeypatch.setattr(system, "task_queue", FakeQueue([]))
    light = FakeLight(fail=True)
    monkeypatch.setattr(system, "DeviceFactory", _fake_factory_class(light))
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.post("/api/emergency-stop")

    assert response.status_code == 200
    body = response.json()
    assert body["laser_off"].startswith("failed:")
    assert "stuck channel 2" in body["laser_off"]
    assert "physical switch" in body["message"]


def test_emergency_stop_manual_light_is_not_applicable(tmp_path, monkeypatch, app_client):
    config_path = _write(tmp_path, BASE["light"])
    queue = FakeQueue(["job-x"])
    monkeypatch.setattr(system, "task_queue", queue)
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", config_path)

    response = app_client.post("/api/emergency-stop")

    assert response.status_code == 200
    body = response.json()
    assert body["laser_off"] == "not_applicable"
    # Jobs are still cancelled even when there's no light to act on.
    assert queue.cancel_all_called is True
    assert body["jobs_cancelled"] == ["job-x"]


def test_emergency_stop_missing_devices_config_reports_failure(tmp_path, monkeypatch, app_client):
    monkeypatch.setattr(system, "task_queue", FakeQueue([]))
    missing = tmp_path / "no-such-devices.yaml"
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", str(missing))

    response = app_client.post("/api/emergency-stop")

    assert response.status_code == 200
    assert response.json()["laser_off"].startswith("failed:")
    assert "physical switch" in response.json()["message"]


def test_emergency_stop_always_cancels_jobs_even_before_config_load(tmp_path, monkeypatch, app_client):
    # Job cancellation must happen unconditionally, before any config/hardware
    # concern -- it's the first, cheapest, most-certain-to-succeed action.
    monkeypatch.setattr(system, "task_queue", FakeQueue(["job-1"]))
    broken = tmp_path / "devices.yaml"
    broken.write_text("not: [valid, yaml, mapping", encoding="utf-8")
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", str(broken))

    response = app_client.post("/api/emergency-stop")

    assert response.status_code == 200
    body = response.json()
    assert body["jobs_cancelled"] == ["job-1"]
    assert body["laser_off"].startswith("failed:")


def test_emergency_stop_prefers_active_light_handle_without_config(tmp_path, monkeypatch, app_client):
    queue = FakeQueue(["job-1"], active_light=True)
    monkeypatch.setattr(system, "task_queue", queue)
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", str(tmp_path / "missing.yaml"))

    response = app_client.post("/api/emergency-stop")

    assert response.status_code == 200
    assert response.json()["laser_off"] == "confirmed"
    assert queue.force_off_called is True
