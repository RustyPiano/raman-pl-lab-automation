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


def test_missing_file_raises():
    with pytest.raises(ConfigError):
        load_tray_scan_config(Path("configs/does_not_exist.yaml"))
