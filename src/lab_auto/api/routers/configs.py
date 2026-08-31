"""Configuration management API endpoints."""
import logging
from typing import Literal

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lab_auto.api.models import ConfigListResponse, ConfigValidationResponse
from lab_auto.api.paths import config_root, resolve_config_path
from lab_auto.config import (
    load_devices_config,
    load_tray_scan_config,
    load_workflow_config,
    workflow_config_from_tray_scan,
)
from lab_auto.errors import ConfigError
from lab_auto.workflow.raman import RamanWorkflow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/configs", tags=["configs"])


@router.get("", response_model=ConfigListResponse)
async def list_configs(config_type: Literal["all", "single_point", "tray"] = "all"):
    """List available configuration files."""
    try:
        config_path = config_root()
        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"Config directory not found: {config_path}")

        yaml_files = []
        for path in [*config_path.rglob("*.yaml"), *config_path.rglob("*.yml")]:
            if config_type in ("single_point", "tray"):
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error listing configs")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/{name:path}")
async def get_config(name: str):
    """Read a configuration file.

    Security: This endpoint uses Path.resolve() and relative_to() to prevent
    path traversal attacks, including symlinks, URL encoding, and Windows paths.
    """
    try:
        try:
            config_path = resolve_config_path(name)
        except ConfigError:
            logger.warning("Invalid configuration path blocked: %s", name)
            raise HTTPException(status_code=400, detail="Invalid config path")

        if not config_path.is_file():
            raise HTTPException(status_code=404, detail=f"Config not found: {name}")

        content = config_path.read_text(encoding="utf-8")
        return {"name": name, "content": content}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error reading config")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


class ConfigValidateRequest(BaseModel):
    """Request to validate a configuration."""
    config_path: str
    config_type: str  # "workflow" or "devices"


@router.post("/validate", response_model=ConfigValidationResponse)
async def validate_config(request: ConfigValidateRequest):
    """Validate a configuration file."""
    try:
        errors = []
        try:
            config_path = resolve_config_path(request.config_path)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        if request.config_type == "devices":
            try:
                load_devices_config(config_path)
            except ConfigError as e:
                errors.append(str(e))
        elif request.config_type == "workflow":
            try:
                load_workflow_config(config_path)
            except ConfigError as e:
                errors.append(str(e))
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid config_type: {request.config_type}. Must be 'workflow' or 'devices'",
            )

        return ConfigValidationResponse(
            valid=len(errors) == 0,
            errors=errors if errors else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error validating config")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
