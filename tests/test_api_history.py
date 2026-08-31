import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from lab_auto.api.routers import history


def _write_run(root, record_id="run-001", warnings=None):
    run_dir = root / record_id
    run_dir.mkdir()
    (run_dir / "metadata.json").write_text(
        json.dumps({
            "timestamp": "2026-08-30T10:00:00+00:00",
            "sample_id": "sample-001",
            "operator": "lab",
            "runtime_mode": "simulated",
            "warnings": ["demo warning"] if warnings is None else warnings,
        }),
        encoding="utf-8",
    )
    (run_dir / "raw.csv").write_text(
        "pixel_index,intensity_raw\n0,1.0\n1,2.0\n",
        encoding="utf-8",
    )
    (run_dir / "run.log").write_text("complete\n", encoding="utf-8")
    return run_dir


def test_history_lists_reads_and_downloads_persisted_measurement(tmp_path, monkeypatch):
    _write_run(tmp_path)
    monkeypatch.setenv("LAB_AUTO_MEASUREMENTS_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(history.router)
    client = TestClient(app)

    listing = client.get("/api/history")
    detail = client.get("/api/history/run-001")
    download = client.get("/api/history/run-001/files/raw.csv")

    assert listing.status_code == 200
    assert listing.json()[0]["sample_id"] == "sample-001"
    assert listing.json()[0]["files"] == ["raw.csv", "metadata.json", "run.log"]
    assert detail.status_code == 200
    assert detail.json()["result"]["spectrum"]["raw"] == [1.0, 2.0]
    assert download.status_code == 200
    assert download.text.startswith("pixel_index,intensity_raw")


def test_history_normalizes_malformed_warnings(tmp_path, monkeypatch):
    _write_run(tmp_path, warnings="legacy warning")
    monkeypatch.setenv("LAB_AUTO_MEASUREMENTS_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(history.router)
    client = TestClient(app)

    listing = client.get("/api/history")
    detail = client.get("/api/history/run-001")

    assert listing.json()[0]["warnings_count"] == 0
    assert detail.status_code == 200
    assert detail.json()["result"]["warnings"] == []
    assert detail.json()["result"]["metadata"]["warnings"] == []


def test_history_skips_invalid_records_and_confines_record_paths(tmp_path, monkeypatch):
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "metadata.json").write_text("not-json", encoding="utf-8")
    outside = tmp_path.parent / "outside-run"
    outside.mkdir(exist_ok=True)
    monkeypatch.setenv("LAB_AUTO_MEASUREMENTS_DIR", str(tmp_path))
    app = FastAPI()
    app.include_router(history.router)

    assert TestClient(app).get("/api/history").json() == []
    with pytest.raises(HTTPException) as exc_info:
        history._record_dir("../outside-run")
    assert exc_info.value.status_code == 404
