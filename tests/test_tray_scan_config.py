from pathlib import Path

import pytest

from lab_auto.config import (
    AcquisitionConfig,
    Calibration,
    OpticsConfig,
    OutputConfig,
    SampleConfig,
    ScanPattern,
    TrayLayout,
    TrayScanConfig,
    load_tray_scan_config,
)
from lab_auto.errors import ConfigError

EXAMPLE = Path("configs/tray_scan.example.yaml")


def test_load_example_config():
    cfg = load_tray_scan_config(EXAMPLE)
    assert isinstance(cfg, TrayScanConfig)
    assert isinstance(cfg.devices_config, Path)
    assert isinstance(cfg.sample, SampleConfig)
    assert isinstance(cfg.optics, OpticsConfig)
    assert isinstance(cfg.acquisition, AcquisitionConfig)
    assert isinstance(cfg.output, OutputConfig)
    assert isinstance(cfg.tray, TrayLayout)
    assert isinstance(cfg.pattern, ScanPattern)
    assert isinstance(cfg.calibration, Calibration)
    assert cfg.on_out_of_range in ("skip", "abort")
    assert cfg.min_area >= 1
    # pattern wiring is internally consistent
    assert cfg.pattern.surrounding_count == len(cfg.pattern.surrounding_angles_deg)
    assert cfg.pattern.repeats_per_point >= 2


def _write(tmp_path, body):
    p = tmp_path / "scan.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def _valid_body():
    return (EXAMPLE).read_text(encoding="utf-8")


def test_unknown_on_out_of_range_rejected(tmp_path):
    body = _valid_body().replace("on_out_of_range: skip", "on_out_of_range: explode")
    with pytest.raises(ConfigError):
        load_tray_scan_config(_write(tmp_path, body))


def test_missing_field_rejected(tmp_path):
    body = "\n".join(
        line for line in _valid_body().splitlines() if not line.startswith("tray:") and "rows:" not in line
    )
    with pytest.raises(ConfigError):
        load_tray_scan_config(_write(tmp_path, body))


def test_pattern_count_mismatch_rejected(tmp_path):
    body = _valid_body().replace("surrounding_count: 2", "surrounding_count: 3")
    with pytest.raises(ConfigError):
        load_tray_scan_config(_write(tmp_path, body))


def test_singular_calibration_matrix_rejected(tmp_path):
    body = _valid_body().replace("a22: 0.5", "a22: 0.0")  # det = 0.5*0 - 0*0 = 0
    with pytest.raises(ConfigError):
        load_tray_scan_config(_write(tmp_path, body))


def test_missing_file_raises():
    with pytest.raises(ConfigError):
        load_tray_scan_config(Path("configs/does_not_exist.yaml"))


def test_negative_burn_threshold_rejected(tmp_path):
    body = _valid_body().replace("burn_threshold: 0.1", "burn_threshold: -0.1")
    with pytest.raises(ConfigError):
        load_tray_scan_config(_write(tmp_path, body))


def test_zero_burn_threshold_rejected(tmp_path):
    # threshold 0 would flag every point as burned
    body = _valid_body().replace("burn_threshold: 0.1", "burn_threshold: 0")
    with pytest.raises(ConfigError):
        load_tray_scan_config(_write(tmp_path, body))


def test_path_injecting_sample_id_rejected(tmp_path):
    body = _valid_body().replace("id: tray-001", "id: ../../etc/evil")
    with pytest.raises(ConfigError):
        load_tray_scan_config(_write(tmp_path, body))


def test_near_singular_calibration_rejected(tmp_path):
    # a11=0.5,a22=0.5,a12/a21=0 -> det 0.25; nudge to make det ~1e-13 (near-singular)
    body = _valid_body().replace("a11: 0.5", "a11: 2e-13").replace("a22: 0.5", "a22: 1.0")
    body = body.replace("a12: 0.0", "a12: 0.0").replace("a21: 0.0", "a21: 0.0")
    with pytest.raises(ConfigError):
        load_tray_scan_config(_write(tmp_path, body))


def test_calibration_image_dimensions_must_be_declared_together(tmp_path):
    body = _valid_body().replace("  image_center_py: 240", "  image_center_py: 240\n  image_width_px: 640")

    with pytest.raises(ConfigError, match="must be set together"):
        load_tray_scan_config(_write(tmp_path, body))


def test_calibration_image_center_must_be_inside_declared_frame(tmp_path):
    body = _valid_body().replace(
        "  image_center_py: 240",
        "  image_center_py: 240\n  image_width_px: 320\n  image_height_px: 480",
    )

    with pytest.raises(ConfigError, match="image_center_px"):
        load_tray_scan_config(_write(tmp_path, body))
