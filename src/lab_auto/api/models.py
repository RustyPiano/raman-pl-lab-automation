"""Pydantic models for API requests and responses."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SinglePointRequest(BaseModel):
    """Request to start a single-point Raman measurement."""
    config_path: str = Field(..., description="Path to workflow config YAML")
    devices_path: str | None = Field(None, description="Override devices config path")
    sample_id: str | None = Field(None, description="Override sample ID")
    mode: Literal["dry_run", "simulated", "real"] = Field("real", description="Execution mode")


class JobProgress(BaseModel):
    """Progress information for a running job."""
    current_step: str | None = None
    total_steps: int | None = None
    completed_steps: int = 0
    message: str | None = None
    percentage: float | None = None


class JobStatus(BaseModel):
    """Status of a workflow job."""
    id: str
    type: str
    status: Literal["pending", "running", "completed", "failed", "stopped"]
    progress: JobProgress
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None


class DeviceStatusResponse(BaseModel):
    """Status of all devices."""
    runtime_mode: str
    scan: dict[str, Any]
    doctor: dict[str, Any]


class LightStatusResponse(BaseModel):
    """Light source status."""
    type: str
    is_on: bool | None = None
    manual_control: bool
    available: bool


class ConfigListResponse(BaseModel):
    """List of available configuration files."""
    configs: list[str]


class ConfigValidationResponse(BaseModel):
    """Configuration validation result."""
    valid: bool
    errors: list[str] | None = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    timestamp: str
