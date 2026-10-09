"""Pydantic models for API requests and responses."""
from typing import Any, Literal

from pydantic import BaseModel, Field


class SinglePointRequest(BaseModel):
    """Request to start a single-point Raman measurement."""
    config_path: str = Field(..., description="Path to workflow config YAML")
    devices_path: str | None = Field(None, description="Override devices config path")
    sample_id: str | None = Field(None, description="Override sample ID")
    operator: str | None = Field(None, description="Override operator name")
    subtract_background: bool | None = Field(None, description="Override background subtraction")
    mode: Literal["dry_run", "simulated", "real"] = Field("dry_run", description="Execution mode")
    confirm_real: bool = Field(False, description="Explicit confirmation for real hardware mode")


class TrayPreviewRequest(BaseModel):
    """Request a side-effect-free tray scan plan."""
    config_path: str = Field(..., description="Path to tray-scan config YAML")


class TrayPreviewResponse(BaseModel):
    """Validated tray geometry and dry-run actions; never touches hardware."""
    config_path: str
    sample_id: str
    operator: str
    layout: dict[str, Any]
    pattern: dict[str, Any]
    wafers: list[dict[str, Any]]
    actions: list[str]
    summary: dict[str, int]
    real_available: bool
    real_unavailable_reason: str


class JobProgress(BaseModel):
    """Progress information for a running job."""
    current_step: str | None = None
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
    mode: Literal["dry_run", "simulated", "real"] | None = None
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


class HistoryRecord(BaseModel):
    """One persisted single-point measurement."""
    id: str
    source: Literal["measurement"] = "measurement"
    type: Literal["single_point"] = "single_point"
    status: Literal["completed", "failed", "stopped"] = "completed"
    error: str | None = None
    created_at: str
    completed_at: str | None
    sample_id: str | None = None
    operator: str | None = None
    mode: str
    warnings_count: int
    files: list[str]


class HistoryDetail(BaseModel):
    """Persisted record metadata plus chart-ready spectrum data."""
    record: HistoryRecord
    result: dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    timestamp: str
