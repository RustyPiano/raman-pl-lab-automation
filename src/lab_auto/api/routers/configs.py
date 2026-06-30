"""Configuration management API endpoints."""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from lab_auto.api.models import ConfigListResponse, ConfigValidationResponse
from lab_auto.config import load_devices_config, load_workflow_config
from lab_auto.errors import ConfigError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/configs", tags=["configs"])


@router.get("", response_model=ConfigListResponse)
async def list_configs(config_dir: str = "configs"):
    """List available configuration files."""
    try:
        config_path = Path(config_dir)
        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"Config directory not found: {config_dir}")

        yaml_files = sorted([
            str(f.relative_to(config_path))
            for f in config_path.rglob("*.yaml")
        ])

        return ConfigListResponse(configs=yaml_files)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error listing configs")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/{name:path}")
async def get_config(name: str, config_dir: str = "configs"):
    """Read a configuration file.

    Security: This endpoint uses Path.resolve() and relative_to() to prevent
    path traversal attacks, including symlinks, URL encoding, and Windows paths.
    """
    try:
        # Resolve base directory to absolute path (follows symlinks)
        config_base = Path(config_dir).resolve()

        # Resolve requested path to absolute path
        config_path = (config_base / name).resolve()

        # Security: Ensure final path is within the allowed directory
        # This check prevents:
        # - Path traversal: ../../../etc/passwd
        # - Symlink escapes: configs/link -> /etc/passwd
        # - Windows paths: C:\Windows\System32\config
        # - URL encoding: ..%2F..%2Fetc%2Fpasswd
        try:
            config_path.relative_to(config_base)
        except ValueError:
            logger.warning(f"Path traversal attempt blocked: {name} -> {config_path}")
            raise HTTPException(status_code=400, detail="Invalid config path")

        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"Config not found: {name}")

        # Security: Only allow YAML files (prevent reading .git/config, .env, etc.)
        if config_path.suffix not in {".yaml", ".yml"}:
            raise HTTPException(status_code=400, detail="Only YAML files are supported")

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

        if request.config_type == "devices":
            try:
                load_devices_config(Path(request.config_path))
            except ConfigError as e:
                errors.append(str(e))
        elif request.config_type == "workflow":
            try:
                load_workflow_config(Path(request.config_path))
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
