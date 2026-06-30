import pytest

from lab_auto.errors import ConfigError
from lab_auto.web import list_workflow_configs, run_job

CONFIG = "configs/single_point.example.yaml"


def test_lists_single_point_configs_only():
    names = list_workflow_configs("configs")
    assert "single_point.example.yaml" in names
    assert "tray_scan.example.yaml" not in names  # has tray: -> excluded
    assert "devices.example.yaml" not in names    # no optics/acquisition


def test_dry_run_returns_actions_and_applies_sample_override():
    result = run_job(config_path=CONFIG, mode="dry_run", sample_id="web-test")
    assert result["mode"] == "dry_run"
    assert result["sample_id"] == "web-test"
    assert any(a.startswith("set_grating") for a in result["actions"])
    assert "save_outputs" in result["actions"]


def test_unknown_mode_is_config_error():
    with pytest.raises(ConfigError):
        run_job(config_path=CONFIG, mode="bogus")


def test_bad_sample_id_rejected_by_config_layer():
    # sample.id path-injection guard still applies through the web override.
    with pytest.raises(ConfigError):
        run_job(config_path=CONFIG, mode="dry_run", sample_id="../evil")
