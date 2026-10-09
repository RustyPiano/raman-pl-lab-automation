import hashlib
import json
from datetime import datetime, timezone

import pytest
from PIL import Image

from lab_auto.config import Calibration
from lab_auto.errors import ConfigError, WorkflowCancelled
from lab_auto.scan.tray import WaferCenter
from lab_auto.storage import write_json
from lab_auto.vision.mask_centers import extract_centers
from lab_auto.vision.recognition import FileMaskProvider, _grid_from_pixels, load_mask
import lab_auto.vision.recognition as recognition

CALIBRATION = Calibration(
    objective="50x", a11=1, a12=0, a21=0, a22=1,
    image_center_px=1, image_center_py=1, image_width_px=3, image_height_px=2,
)
WAFER = WaferCenter(x_um=0, y_um=0, row=0, col=0, index=0)


def test_grid_threshold_rejects_below_and_keeps_above():
    # threshold 127: 100 -> background, 200 -> foreground.
    grid = _grid_from_pixels([100, 200, 0, 255], width=2)
    assert grid == [[0, 1], [0, 1]]


def test_load_mask_binary_png_roundtrips(tmp_path):
    # 0/255 mask: one foreground pixel; threshold 127 keeps it, extract finds 1 center.
    img = Image.new("L", (3, 2), 0)
    img.putpixel((1, 0), 255)
    path = tmp_path / "m.png"
    img.save(path)
    mask = load_mask(path)
    assert mask == [[0, 1, 0], [0, 0, 0]]
    assert len(extract_centers(mask)) == 1


@pytest.mark.parametrize("broken", [None, "session_id", "request_id", "wafer_index", "captured_at", "mask_sha256", "measurement_ready", "objective", "capture_size"])
def test_session_handshake_accepts_only_matching_fresh_artifacts(tmp_path, monkeypatch, broken):
    provider = FileMaskProvider(tmp_path, session_id="tray-session", timeout_s=0.1, calibration=CALIBRATION)

    def respond(path, request):
        write_json(path, request)
        receipt = {
            "session_id": request["session_id"], "request_id": request["request_id"],
            "wafer_index": request["wafer"]["index"],
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "measurement_ready": True,
            "objective": "50x",
        }
        for kind in ("capture", "mask"):
            artifact = path.parent / request[f"{kind}_file"]
            size = (4, 2) if broken == "capture_size" and kind == "capture" else (3, 2)
            Image.new("L", size, 255).save(artifact)
            receipt[f"{kind}_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if broken:
            receipt[broken] = "2000-01-01T00:00:00+00:00" if broken == "captured_at" else "wrong"
        write_json(path.parent / request["response_file"], receipt)

    monkeypatch.setattr(recognition, "write_json", respond)
    if broken:
        with pytest.raises(ConfigError):
            provider(WAFER)
        assert provider.last_receipt is None
    else:
        assert provider(WAFER) == [[1, 1, 1], [1, 1, 1]]
        assert provider.last_receipt["session_id"] == "tray-session"
        request = json.loads((tmp_path / "tray-session" / "0.request.json").read_text())
        assert request["request_id"] == provider.last_receipt["request_id"]


def test_session_wait_can_be_cancelled_and_does_not_consume_old_mask(tmp_path):
    provider = FileMaskProvider(tmp_path, session_id="session", timeout_s=0.1, calibration=CALIBRATION)
    provider.should_cancel = lambda: True
    with pytest.raises(WorkflowCancelled):
        provider(WAFER)


def test_session_times_out_instead_of_loading_a_previous_static_mask(tmp_path):
    Image.new("L", (2, 2), 255).save(tmp_path / "0.png")
    provider = FileMaskProvider(tmp_path, session_id="new-session", timeout_s=0.01, calibration=CALIBRATION)
    with pytest.raises(ConfigError, match="timed out"):
        provider(WAFER)
