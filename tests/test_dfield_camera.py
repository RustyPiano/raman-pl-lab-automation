import math
from pathlib import Path

import pytest

from lab_auto.devices.dfield_camera import DFieldCamera, gain_to_code, read_mode_to_code
from lab_auto.errors import ConfigError, DeviceError


def test_gain_mapping_matches_header():
    assert gain_to_code("high") == 0
    assert gain_to_code("low") == 1


def test_read_mode_mapping_matches_header():
    assert read_mode_to_code("fvb") == 0
    assert read_mode_to_code("image") == 1


def test_adapter_close_calls_raw_client_not_native_symbol():
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)

    camera.close()

    assert raw.closed is True


def test_adapter_exposes_phase1_status_capture_and_csv(tmp_path: Path):
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)
    out = tmp_path / "capture.csv"

    status = camera.status()
    frame = camera.capture(read_mode="fvb", exposure_ms=1000, gain="low", frames=1)
    camera.capture_to_csv(mode="fvb", exposure_ms=1000, gain="low", out=out)

    assert status == {"open": True, "width": 3, "height": 1, "gain": "low", "read_mode": "fvb"}
    assert "gain_code" not in status
    assert "read_mode_code" not in status
    assert frame.width == 3
    assert frame.height == 1
    assert frame.bin_x == 1
    assert frame.bin_y == 1
    assert frame.roi is None
    assert frame.values == [100, 101, 102]
    assert frame.raw_frames_count == 1
    assert frame.saturation_threshold == 65535
    assert frame.metadata["detector_width"] == 3
    assert frame.metadata["detector_height"] == 1
    assert raw.calls == [
        ("status",),
        ("capture", 0, 1000, 1, 1, 1, 1, None),
        ("capture", 0, 1000, 1, 1, 1, 1, None),
    ]
    assert out.read_text(encoding="utf-8").splitlines()[0] == "pixel_index,intensity_raw,saturated"


def test_adapter_does_not_write_csv_when_capture_fails(tmp_path: Path):
    raw = FakeDFieldRaw(fail_capture=True)
    camera = DFieldCamera(raw)
    out = tmp_path / "capture.csv"

    with pytest.raises(DeviceError, match="capture failed"):
        camera.capture_to_csv(mode="fvb", exposure_ms=1000, gain="low", out=out)

    assert not out.exists()


def test_image_capture_csv_uses_row_col_schema(tmp_path: Path):
    raw = FakeImageRaw()
    camera = DFieldCamera(raw)
    out = tmp_path / "image.csv"

    camera.capture_to_csv(mode="image", exposure_ms=100, gain="low", out=out)

    assert out.read_text(encoding="utf-8").splitlines() == [
        "row,col,intensity_raw,saturated",
        "0,0,10,false",
        "0,1,11,true",
        "1,0,12,false",
        "1,1,13,false",
    ]


def test_adapter_preserves_detector_dimensions_for_binned_capture():
    raw = FakeBinnedRaw()
    camera = DFieldCamera(raw)

    frame = camera.capture(read_mode="image", exposure_ms=100, gain="low", frames=1)

    assert frame.width == 2
    assert frame.metadata["detector_width"] == 4
    assert frame.metadata["detector_height"] == 4


def test_adapter_passes_requested_bin_and_roi_to_raw():
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)

    camera.capture(read_mode="image", exposure_ms=100, gain="low", frames=2, bin_x=2, bin_y=3, roi=(1, 4, 3, 6))

    assert raw.calls == [("capture", 1, 100, 1, 2, 2, 3, (1, 4, 3, 6))]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"bin_x": 0},
        {"bin_x": 65},
        {"bin_y": 0},
        {"bin_y": 130},
        {"roi": (2, 1, 0, 7)},
        {"roi": (0, math.nan, 0, 1)},
        {"roi": (0, 1.5, 0, 1)},
        {"roi": (True, 1, 0, 1)},
    ],
)
def test_adapter_validates_bin_and_roi_before_raw_capture(kwargs):
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)

    with pytest.raises(ConfigError):
        camera.capture(read_mode="image", exposure_ms=100, gain="low", frames=1, **kwargs)

    assert raw.calls == []


def test_adapter_rejects_fvb_roi_before_raw_capture():
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)

    with pytest.raises(ConfigError, match="ROI"):
        camera.capture(read_mode="fvb", exposure_ms=100, gain="low", frames=1, roi=(0, 1, 0, 0))

    assert raw.calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"exposure_ms": 60_001},
        {"frames": 1001},
        {"exposure_ms": 1000, "frames": 61},
    ],
)
def test_adapter_rejects_capture_args_over_safety_caps(kwargs):
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)

    args = {"read_mode": "fvb", "exposure_ms": 100, "gain": "low", "frames": 1}
    args.update(kwargs)
    with pytest.raises(ConfigError, match="safety cap"):
        camera.capture(**args)

    assert raw.calls == []


def test_adapter_accepts_capture_args_at_safety_caps():
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)

    frame = camera.capture(read_mode="fvb", exposure_ms=60_000, gain="low", frames=1)
    assert frame is not None


@pytest.mark.parametrize("kwargs", [{"frames": math.nan}, {"frames": 1, "bin_x": math.nan}, {"frames": 1, "bin_y": math.nan}])
def test_adapter_rejects_non_finite_integer_capture_args(kwargs):
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)
    frames = kwargs.pop("frames")

    with pytest.raises(ConfigError):
        camera.capture(read_mode="image", exposure_ms=100, gain="low", frames=frames, **kwargs)

    assert raw.calls == []


def test_adapter_rejects_huge_integer_exposure():
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)

    with pytest.raises(ConfigError, match="exposure"):
        camera.capture(read_mode="image", exposure_ms=10**400, gain="low", frames=1)

    assert raw.calls == []


def test_adapter_rejects_float32_overflow_exposure():
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)

    with pytest.raises(ConfigError, match="exposure"):
        camera.capture(read_mode="image", exposure_ms=1e39, gain="low", frames=1)

    assert raw.calls == []


def test_adapter_rejects_float32_underflow_exposure():
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)

    with pytest.raises(ConfigError, match="exposure"):
        camera.capture(read_mode="image", exposure_ms=1e-46, gain="low", frames=1)

    assert raw.calls == []


def test_adapter_exposes_temperature():
    raw = FakeDFieldRaw()
    camera = DFieldCamera(raw)

    assert camera.temperature_c() == 23.5
    assert raw.calls == [("temperature_c",)]


class FakeDFieldRaw:
    def __init__(self, *, fail_capture=False):
        self.closed = False
        self.calls = []
        self.fail_capture = fail_capture

    def status(self) -> dict:
        self.calls.append(("status",))
        return {"open": True, "width": 3, "height": 1, "gain_code": 1, "read_mode_code": 0}

    def capture(self, *, read_mode_code: int, exposure_ms: float, gain_code: int, frames: int, bin_x: int = 1, bin_y: int = 1, roi=None, should_cancel=None) -> dict:
        self.calls.append(("capture", read_mode_code, exposure_ms, gain_code, frames, bin_x, bin_y, roi))
        if self.fail_capture:
            raise DeviceError("DField capture failed")
        return {
            "width": 3,
            "height": 1,
            "detector_width": 3,
            "detector_height": 1,
            "bin_x": 1,
            "bin_y": 1,
            "roi": None,
            "values": [100, 101, 102],
            "saturated": [False, False, False],
            "raw_frames_count": frames,
            "saturation_threshold": 65535,
        }

    def close(self) -> None:
        self.closed = True

    def temperature_c(self) -> float:
        self.calls.append(("temperature_c",))
        return 23.5


class FakeImageRaw:
    def capture(self, *, read_mode_code: int, exposure_ms: float, gain_code: int, frames: int, bin_x: int = 1, bin_y: int = 1, roi=None, should_cancel=None) -> dict:
        return {
            "width": 2,
            "height": 2,
            "detector_width": 2,
            "detector_height": 2,
            "bin_x": 1,
            "bin_y": 1,
            "roi": None,
            "values": [10, 11, 12, 13],
            "saturated": [False, True, False, False],
            "raw_frames_count": frames,
            "saturation_threshold": 65535,
        }

    def close(self) -> None:
        pass


class FakeBinnedRaw(FakeImageRaw):
    def capture(self, *, read_mode_code: int, exposure_ms: float, gain_code: int, frames: int, bin_x: int = 1, bin_y: int = 1, roi=None, should_cancel=None) -> dict:
        data = super().capture(
            read_mode_code=read_mode_code,
            exposure_ms=exposure_ms,
            gain_code=gain_code,
            frames=frames,
            bin_x=bin_x,
            bin_y=bin_y,
            roi=roi,
        )
        data["detector_width"] = 4
        data["detector_height"] = 4
        return data
