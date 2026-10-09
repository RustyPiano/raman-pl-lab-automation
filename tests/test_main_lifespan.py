"""Tests for the FastAPI lifespan startup/shutdown safety reset (api/main.py).

The startup reset must never block the API from serving requests, even when
there's no default devices config (the common dev-machine case) or the
config fails to load. Real hardware is never touched here.
"""
from fastapi.testclient import TestClient
import pytest

import lab_auto.api.main as main


def test_app_starts_when_no_default_devices_config_present(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", str(tmp_path / "no-such-devices.yaml"))

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_app_starts_even_if_devices_config_fails_to_load(tmp_path, monkeypatch):
    broken = tmp_path / "devices.yaml"
    broken.write_text("not: [valid, yaml, mapping", encoding="utf-8")
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", str(broken))

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200


def test_reset_light_best_effort_reports_missing_default_config(tmp_path):
    success, detail = main._reset_light_best_effort(tmp_path / "missing.yaml")

    assert success is False
    assert "not found" in detail


def test_reset_light_best_effort_is_success_for_manual_light(tmp_path, monkeypatch):
    import yaml

    devices_yaml = {
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
    config_path = tmp_path / "devices.yaml"
    config_path.write_text(yaml.safe_dump(devices_yaml), encoding="utf-8")
    success, detail = main._reset_light_best_effort(config_path)

    assert success is True
    assert "no hardware to reset" in detail


def test_reset_light_best_effort_reports_failure_without_raising(tmp_path, monkeypatch):
    broken = tmp_path / "devices.yaml"
    broken.write_text("not: [valid, yaml, mapping", encoding="utf-8")
    success, detail = main._reset_light_best_effort(broken)

    assert success is False
    assert detail  # some reason is reported, never a silent failure


def test_atexit_handler_never_raises(tmp_path, monkeypatch):
    # The atexit-registered handler must swallow everything -- process exit
    # must never be blocked by this safety net.
    monkeypatch.setenv("LAB_AUTO_DEVICES_CONFIG", str(tmp_path / "missing.yaml"))

    main._atexit_safety_reset()  # must not raise


def test_corrupt_job_history_cannot_bypass_startup_light_reset(tmp_path, monkeypatch):
    from lab_auto.errors import ConfigError

    path = tmp_path / "jobs.json"
    monkeypatch.setattr(main, "_atexit_reset_armed", False)
    path.write_text("broken-json")
    monkeypatch.setenv("LAB_AUTO_JOB_STATE", str(path))
    resets = []

    def reset():
        resets.append(True)
        return True, "fake light confirmed off"

    monkeypatch.setattr(main, "_reset_light_best_effort", reset)
    with pytest.raises(ConfigError, match="recover"):
        with TestClient(main.app):
            pass
    assert resets == [True]
