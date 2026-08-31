from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lab_auto.api.routers import workflow


def test_tray_preview_returns_validated_geometry_and_plan(tmp_path, monkeypatch):
    source = Path(__file__).parents[1] / "configs" / "tray_scan.example.yaml"
    config_text = source.read_text(encoding="utf-8").replace("min_area: 5", "min_area: 10")
    (tmp_path / "tray.yaml").write_text(config_text, encoding="utf-8")
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(workflow.router)

    response = TestClient(app).post("/api/workflow/tray/preview", json={"config_path": "tray.yaml"})

    assert response.status_code == 200
    body = response.json()
    assert body["layout"] == {
        "rows": 2,
        "cols": 2,
        "pitch_x_um": 2000.0,
        "pitch_y_um": 2000.0,
        "order": "serpentine",
    }
    assert [(wafer["row"], wafer["col"]) for wafer in body["wafers"]] == [
        (0, 0), (0, 1), (1, 1), (1, 0)
    ]
    assert body["summary"] == {
        "wafer_count": 4,
        "sample_centers": 4,
        "measurement_points": 12,
        "acquisitions": 24,
        "burn_checks": 12,
        "action_count": 60,
    }
    assert body["real_available"] is False


def test_tray_preview_rejects_unsafe_single_point_settings(tmp_path, monkeypatch):
    source = Path(__file__).parents[1] / "configs" / "tray_scan.example.yaml"
    config_text = source.read_text(encoding="utf-8").replace("exposure_ms: 1000", "exposure_ms: -1")
    (tmp_path / "tray.yaml").write_text(config_text, encoding="utf-8")
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(workflow.router)

    response = TestClient(app).post("/api/workflow/tray/preview", json={"config_path": "tray.yaml"})

    assert response.status_code == 400
    assert "exposure" in response.json()["detail"]


def test_tray_preview_rejects_path_outside_config_root(tmp_path, monkeypatch):
    config_root = tmp_path / "configs"
    config_root.mkdir()
    outside = tmp_path / "tray.yaml"
    outside.write_text("tray: {}\n", encoding="utf-8")
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(config_root))
    app = FastAPI()
    app.include_router(workflow.router)

    response = TestClient(app).post(
        "/api/workflow/tray/preview",
        json={"config_path": str(outside)},
    )

    assert response.status_code == 400
