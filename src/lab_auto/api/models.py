"""Pydantic models for API requests and responses."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SinglePointRequest(BaseModel):
    """Request to start a single-point Raman measurement."""
    config_path: str = Field(..., description="Path to workflow config YAML")
    devices_path: str | None = Field(None, description="Override devices config path")
    sample_id: str | None = Field(None, description="Override sample ID")
    mode: Literal["dry_run", "simulated", "real"] = Field("dry_run", description="Execution mode")
    confirm_real: bool = Field(False, description="Explicit confirmation for real hardware mode")


class JobProgress(BaseModel):
    """Progress information for a running job."""
    current_step: str | None = None
    total_steps: int | None = None
    completed_steps: int = 0
    message: str | None = None
    percentage: float | None = None


class JobStatus(BaseModel):
    """Status of a workflow job.

    ``stopping`` is transitional: a stop was requested on a running job and its
    cancellation signal was raised, but the workflow has not yet reached a
    checkpoint and unwound. It becomes ``stopped`` once the workflow actually
    halts (or ``completed`` if it finished before the request took effect).
    """
    id: str
    type: str
    status: Literal["pending", "running", "stopping", "completed", "failed", "stopped"]
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
    """Light source status.

    ``hardware_state`` is populated only for a ``pwm_modbus`` light (the
    register read-back from ``PwmModbusLight.read_hardware_state()``); a
    manual light has no hardware to read and reports ``None``.
    """
    type: str
    manual_control: bool
    available: bool
    hardware_state: dict[str, Any] | None = None


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
