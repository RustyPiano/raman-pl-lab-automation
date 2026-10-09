"""Request a recognition mask from the external capture/recognition worker.

The segmentation (capture colour image -> multi-task U-Net -> mask) runs on a
separate machine; we only receive the finished black/white mask image. Our job
stops at turning that image into the ``2D list[list[int]]`` that
``extract_centers`` consumes — which is exactly the ``mask_provider(wafer) ->
mask`` seam :class:`TrayScanWorkflow` injects. The file handshake is described
in ``docs/recognition-handoff.md``.
"""

import hashlib
import json
import math
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from lab_auto.config import Calibration, validate_sample_id
from lab_auto.errors import ConfigError, WorkflowCancelled
from lab_auto.storage import write_json

# 前景 = 灰度 > 127：0/255 掩码边缘的 JPEG/抗锯齿噪声不会被当成前景
MASK_THRESHOLD = 127


def _grid_from_pixels(pixels, width):
    """Flat grayscale pixel sequence (row-major) -> ``list[list[int]]`` of 0/1."""
    return [
        [1 if pixels[r * width + c] > MASK_THRESHOLD else 0 for c in range(width)]
        for r in range(len(pixels) // width)
    ]


def load_mask(path):
    """Read a mask image file into a 0/1 grid."""
    with Image.open(path) as source:
        img = source.convert("L")  # 8-bit grayscale; handles 0/255 masks
        width, _ = img.size
        pixels = img.tobytes()
    # ponytail: full-res mask -> nested list -> pure-Python flood fill in
    # extract_centers. Fine at these mask sizes; if frames get large and this
    # turns slow, read with numpy + cv2.connectedComponentsWithStats.
    return _grid_from_pixels(pixels, width)


class FileMaskProvider:
    """``mask_provider``: ask the recognition worker for one wafer's fresh mask."""

    def __init__(self, mask_dir, *, session_id: str, calibration: Calibration, timeout_s: float = 60):
        self.mask_dir = Path(mask_dir)
        self.session_id = validate_sample_id(session_id)
        if not math.isfinite(timeout_s) or not 0 < timeout_s <= 300:
            raise ConfigError("recognition timeout must be between 0 and 300 seconds")
        self.timeout_s = timeout_s
        self.calibration = calibration
        self.should_cancel = None
        self.last_receipt = None
        self.identity = {"directory": str(self.mask_dir.resolve()), "session_id": self.session_id}

    def __call__(self, wafer):
        directory = self.mask_dir / self.session_id
        request_id = uuid.uuid4().hex
        requested_at = datetime.now(timezone.utc)
        request = {
            "session_id": self.session_id,
            "request_id": request_id,
            "requested_at": requested_at.isoformat(),
            "wafer": asdict(wafer),
            "calibration": asdict(self.calibration),
            "capture_file": f"{request_id}.capture.png",
            "mask_file": f"{request_id}.mask.png",
            "response_file": f"{request_id}.response.json",
        }
        write_json(directory / f"{wafer.index}.request.json", request)
        response_path = directory / request["response_file"]
        deadline = time.monotonic() + self.timeout_s
        while not response_path.exists():
            if self.should_cancel is not None and self.should_cancel():
                raise WorkflowCancelled("cancelled while waiting for recognition")
            if time.monotonic() >= deadline:
                raise ConfigError(f"recognition timed out waiting for {response_path}")
            time.sleep(0.05)
        if self.should_cancel is not None and self.should_cancel():
            raise WorkflowCancelled("cancelled before accepting recognition")
        # 回执来自外部程序：任何解析或校验失败都统一报告为 ConfigError，便于操作员定位
        try:
            receipt = json.loads(response_path.read_text(encoding="utf-8"))
            captured_at = datetime.fromisoformat(receipt["captured_at"])
            if (receipt["session_id"] != self.session_id or receipt["request_id"] != request_id
                    or receipt["wafer_index"] != wafer.index):
                raise ConfigError("recognition receipt belongs to another request or wafer")
            if not requested_at <= captured_at <= datetime.now(timezone.utc):
                raise ConfigError("recognition capture timestamp is stale or in the future; synchronize worker clocks")
            if receipt.get("measurement_ready") is not True:
                raise ConfigError("recognition worker has not confirmed the measurement optical path is ready")
            if receipt.get("objective") != self.calibration.objective:
                raise ConfigError("recognition objective differs from the calibrated objective")
            for kind in ("capture", "mask"):
                path = directory / request[f"{kind}_file"]
                if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != receipt[f"{kind}_sha256"]:
                    raise ConfigError(f"recognition {kind} checksum mismatch")
            with Image.open(directory / request["capture_file"]) as capture:
                if capture.size != (self.calibration.image_width_px, self.calibration.image_height_px):
                    raise ConfigError("recognition capture dimensions differ from calibration")
                capture.verify()
            mask = load_mask(directory / request["mask_file"])
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ConfigError(f"invalid recognition receipt: {response_path}: {exc}") from exc
        self.last_receipt = {**receipt, "directory": str(directory.resolve())}
        return mask
