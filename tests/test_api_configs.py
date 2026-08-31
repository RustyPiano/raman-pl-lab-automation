from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lab_auto.api.paths import resolve_config_path
from lab_auto.api.routers import configs
from lab_auto.errors import ConfigError


def test_config_paths_are_confined_to_server_root(tmp_path, monkeypatch):
    config_root = tmp_path / "configs"
    config_root.mkdir()
    safe = config_root / "safe.yaml"
    safe.write_text("ok: true\n", encoding="utf-8")
    outside = tmp_path / "secret.yaml"
    outside.write_text("secret: true\n", encoding="utf-8")
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(config_root))

    assert resolve_config_path("safe.yaml") == safe
    with pytest.raises(ConfigError):
        resolve_config_path("../secret.yaml")
    with pytest.raises(ConfigError):
        resolve_config_path(outside)
    with pytest.raises(ConfigError):
        resolve_config_path("safe.txt")


def test_config_symlink_cannot_escape_server_root(tmp_path, monkeypatch):
    config_root = tmp_path / "configs"
    config_root.mkdir()
    outside = tmp_path / "secret.yaml"
    outside.write_text("secret: true\n", encoding="utf-8")
    link = config_root / "escape.yaml"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable")
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(config_root))

    with pytest.raises(ConfigError):
        resolve_config_path("escape.yaml")


def test_single_point_config_listing_excludes_devices_and_tray(tmp_path, monkeypatch):
    (tmp_path / "single.yaml").write_text(
        "devices_config: devices.yaml\nsample: {}\noptics: {}\nacquisition: {}\noutput: {}\n",
        encoding="utf-8",
    )
    (tmp_path / "devices.yaml").write_text("runtime: {}\nstage: {}\n", encoding="utf-8")
    (tmp_path / "tray.yaml").write_text(
        "devices_config: devices.yaml\nsample: {}\noptics: {}\nacquisition: {}\noutput: {}\ntray: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(configs.router)

    response = TestClient(app).get("/api/configs", params={"config_type": "single_point"})

    assert response.status_code == 200
    assert response.json() == {"configs": ["single.yaml"]}


def test_tray_config_listing_only_returns_valid_tray_configs(tmp_path, monkeypatch):
    valid = Path(__file__).parents[1] / "configs" / "tray_scan.example.yaml"
    (tmp_path / "tray.yaml").write_text(valid.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "unfinished.yaml").write_text(
        valid.read_text(encoding="utf-8").replace("rows: 2", "rows: <FILL>"),
        encoding="utf-8",
    )
    (tmp_path / "unsafe.yaml").write_text(
        valid.read_text(encoding="utf-8").replace("exposure_ms: 1000", "exposure_ms: -1"),
        encoding="utf-8",
    )
    (tmp_path / "single.yaml").write_text(
        "devices_config: devices.yaml\nsample: {}\noptics: {}\nacquisition: {}\noutput: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(configs.router)

    response = TestClient(app).get("/api/configs", params={"config_type": "tray"})

    assert response.status_code == 200
    assert response.json() == {"configs": ["tray.yaml"]}


def test_config_endpoint_ignores_removed_config_dir_override(tmp_path, monkeypatch):
    config_root = tmp_path / "configs"
    config_root.mkdir()
    (config_root / "safe.yaml").write_text("safe: true\n", encoding="utf-8")
    (config_root / "also-safe.yml").write_text("safe: true\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.yaml").write_text("secret: true\n", encoding="utf-8")
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(config_root))
    app = FastAPI()
    app.include_router(configs.router)

    response = TestClient(app).get("/api/configs", params={"config_dir": str(outside)})

    assert response.status_code == 200
    assert response.json() == {"configs": ["also-safe.yml", "safe.yaml"]}
