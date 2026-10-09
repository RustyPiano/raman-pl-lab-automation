"""Server-owned configuration paths for the local API."""

import os
from pathlib import Path

from lab_auto.errors import ConfigError


def config_root() -> Path:
    default = Path(__file__).resolve().parents[3] / "configs"
    return Path(os.environ.get("LAB_AUTO_CONFIG_DIR", default)).resolve()


def default_devices_config_path() -> Path:
    configured = os.environ.get("LAB_AUTO_DEVICES_CONFIG")
    if configured:
        return Path(configured).resolve()
    local = config_root() / "devices.yaml"
    return local if local.exists() else config_root() / "devices.example.yaml"


def measurement_root() -> Path:
    """Directory containing persisted single-point measurement runs."""
    default = Path(__file__).resolve().parents[3] / "output" / "measurements"
    return Path(os.environ.get("LAB_AUTO_MEASUREMENTS_DIR", default)).resolve()


def job_state_path() -> Path:
    default = Path(__file__).resolve().parents[3] / "state" / "api_jobs.json"
    return Path(os.environ.get("LAB_AUTO_JOB_STATE", default)).resolve()


def resolve_config_path(value: str | Path) -> Path:
    """Resolve one YAML path inside the server-owned configuration root."""
    try:
        root = config_root()
        raw = Path(value)
        if raw.is_absolute():
            resolved = raw.resolve()
        else:
            resolved = (root.parent / raw).resolve() if raw.parts[:1] == (root.name,) else (root / raw).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ConfigError("invalid configuration path") from exc
    if not resolved.is_relative_to(root):
        raise ConfigError("configuration path must stay inside the configured config directory")
    if resolved.suffix.lower() not in {".yaml", ".yml"}:
        raise ConfigError("only YAML configuration files are supported")
    return resolved
