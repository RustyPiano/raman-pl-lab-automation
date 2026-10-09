"""Configuration listing API endpoint."""
from typing import Literal

import yaml
from fastapi import APIRouter, HTTPException

from lab_auto.api.models import ConfigListResponse
from lab_auto.api.paths import config_root
from lab_auto.config import load_tray_scan_config, workflow_config_from_tray_scan
from lab_auto.errors import ConfigError
from lab_auto.workflow.raman import RamanWorkflow

router = APIRouter(prefix="/api/configs", tags=["configs"])


@router.get("", response_model=ConfigListResponse)
async def list_configs(config_type: Literal["all", "single_point", "tray"] = "all"):
    """List available configuration files."""
    config_path = config_root()
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"Config directory not found: {config_path}")

    yaml_files = []
    for path in [*config_path.rglob("*.yaml"), *config_path.rglob("*.yml")]:
        if config_type in ("single_point", "tray"):
            # 目录里可能有用户放的任意 YAML：读不了或不是目标类型的直接跳过，不让列表接口失败
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, yaml.YAMLError):
                continue
            required = {"devices_config", "sample", "optics", "acquisition", "output"}
            is_tray = isinstance(data, dict) and "tray" in data
            if not isinstance(data, dict) or not required.issubset(data) or is_tray != (config_type == "tray"):
                continue
            if config_type == "tray":
                try:
                    tray_config = load_tray_scan_config(path)
                    RamanWorkflow.dry_run(
                        workflow_config_from_tray_scan(tray_config)
                    ).validate_single_point_config()
                except ConfigError:
                    continue
        yaml_files.append(str(path.relative_to(config_path)))
    yaml_files.sort()

    return ConfigListResponse(configs=yaml_files)
