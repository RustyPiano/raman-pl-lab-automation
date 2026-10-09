"""Workflow execution API endpoints."""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, WebSocketException

from lab_auto.api.models import JobStatus, SinglePointRequest, TrayPreviewRequest, TrayPreviewResponse
from lab_auto.api.paths import resolve_config_path
from lab_auto.api.task_queue import task_queue
from lab_auto.api.websocket import manager
from lab_auto.config import (
    load_devices_config,
    load_tray_scan_config,
    load_workflow_config,
    validate_sample_id,
    workflow_config_from_tray_scan,
)
from lab_auto.errors import ConfigError
from lab_auto.scan.tray import wafer_centers
from lab_auto.workflow.raman import RamanWorkflow
from lab_auto.workflow.tray_scan import TrayScanWorkflow, simulated_mask_provider

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.post("/tray/preview", response_model=TrayPreviewResponse)
async def preview_tray_scan(request: TrayPreviewRequest):
    """Validate and plan a tray scan without opening devices or moving hardware."""
    config_path = resolve_config_path(request.config_path)
    if not config_path.is_file():
        raise HTTPException(status_code=404, detail=f"Config not found: {request.config_path}")
    config = load_tray_scan_config(config_path)
    RamanWorkflow.dry_run(workflow_config_from_tray_scan(config)).validate_single_point_config()
    wafers = wafer_centers(config.tray)
    actions = TrayScanWorkflow.dry_run(
        config,
        mask_provider=simulated_mask_provider(config.min_area),
    ).plan()

    return TrayPreviewResponse(
        config_path=request.config_path,
        sample_id=config.sample.id,
        operator=config.sample.operator,
        layout={
            "rows": config.tray.rows,
            "cols": config.tray.cols,
            "pitch_x_um": config.tray.pitch_x_um,
            "pitch_y_um": config.tray.pitch_y_um,
            "order": config.tray.order,
        },
        pattern={
            "repeats_per_point": config.pattern.repeats_per_point,
            "surrounding_count": config.pattern.surrounding_count,
            "surrounding_distance_um": config.pattern.surrounding_distance_um,
            "burn_threshold": config.pattern.burn_threshold,
        },
        wafers=[
            {
                "index": wafer.index,
                "row": wafer.row,
                "col": wafer.col,
                "x_um": wafer.x_um,
                "y_um": wafer.y_um,
            }
            for wafer in wafers
        ],
        actions=actions,
        summary={
            "wafer_count": len(wafers),
            "sample_centers": sum(action.startswith("return_wafer_center:") for action in actions),
            "measurement_points": sum(action.startswith("move_point:") for action in actions),
            "acquisitions": sum(action.startswith("measure:") for action in actions),
            "burn_checks": sum(action.startswith("burn_check:") for action in actions),
            "action_count": len(actions),
        },
        real_available=False,
        real_unavailable_reason=(
            "Supervised real tray scan is available through the CLI file handshake. "
            "The Web entry remains disabled until optical-path control and on-rig calibration are verified."
        ),
    )


@router.post("/single-point", response_model=JobStatus)
async def start_single_point(request: SinglePointRequest):
    """Start a single-point Raman measurement.

    This is the only entry into the hardware queue, so the real-mode
    confirmation and the overrides are validated here once.
    """
    if request.confirm_real and request.mode != "real":
        raise HTTPException(status_code=400, detail="confirm_real=true is only valid in real mode")
    if request.mode == "real" and not request.confirm_real:
        raise HTTPException(status_code=400, detail="Real mode requires confirm_real=true")

    config_path = resolve_config_path(request.config_path)
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"Config not found: {request.config_path}")
    workflow_config = load_workflow_config(config_path)
    devices_path = resolve_config_path(request.devices_path or workflow_config.devices_config)
    if not devices_path.exists():
        raise HTTPException(status_code=404, detail=f"Devices config not found: {devices_path.name}")
    devices_config = load_devices_config(devices_path)
    RamanWorkflow.dry_run(workflow_config).validate_single_point_config()
    sample_id = validate_sample_id(request.sample_id.strip()) if request.sample_id is not None else None
    operator = request.operator.strip() if request.operator is not None else None
    if operator == "":
        raise ConfigError("operator override cannot be empty")

    # Reject a manual light source up front: its terminal confirmation prompt
    # would hang the server thread. Web real mode needs programmatic control.
    if request.mode == "real" and devices_config.light.type == "manual":
        raise HTTPException(
            status_code=400,
            detail=(
                "Web API real mode requires a pwm_modbus light source; a manual light "
                "needs terminal confirmation which would hang the server"
            ),
        )

    job_id = task_queue.create_job("single_point")
    await task_queue.submit_single_point(
        job_id=job_id,
        config_path=str(config_path),
        devices_path=str(devices_path),
        mode=request.mode,
        confirm_real=request.confirm_real,
        sample_id=sample_id,
        operator=operator,
        subtract_background=request.subtract_background,
    )
    return task_queue.get_job(job_id)


@router.get("/jobs", response_model=list[JobStatus])
async def list_jobs():
    """List all jobs."""
    return task_queue.list_jobs()


@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str):
    """Get job status by ID."""
    job = task_queue.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@router.post("/jobs/{job_id}/stop")
async def stop_job(job_id: str):
    """Request a job to stop.

    A pending job stops immediately; a running job transitions to ``stopping``
    and only becomes ``stopped`` once the workflow halts at a checkpoint. The
    response reports the job's actual status, not a blanket "stopped".
    """
    success = await task_queue.stop_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job cannot be stopped (not found or already completed)")
    return {"status": task_queue.get_job(job_id).status, "job_id": job_id}


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_progress(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job progress updates."""
    job = task_queue.get_job(job_id)
    if job is None:
        raise WebSocketException(code=4404, reason="Job not found")
    await manager.connect(websocket, job_id)
    try:
        await websocket.send_json({
            "type": "status",
            "status": job.status,
            "progress": job.progress.model_dump(),
            "result": job.result,
            "error": job.error,
        })
        # 客户端不发送消息；持续接收只是为了感知断开
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, job_id)
