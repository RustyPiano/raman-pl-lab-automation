"""Workflow execution API endpoints."""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from lab_auto.api.models import JobStatus, SinglePointRequest
from lab_auto.api.task_queue import task_queue
from lab_auto.api.websocket import manager
from lab_auto.config import load_workflow_and_devices
from lab_auto.errors import ConfigError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflow", tags=["workflow"])


@router.post("/single-point", response_model=JobStatus)
async def start_single_point(request: SinglePointRequest):
    """Start a single-point Raman measurement."""
    try:
        # Validate config paths exist
        config_path = Path(request.config_path)
        if not config_path.exists():
            raise HTTPException(status_code=404, detail=f"Config not found: {request.config_path}")

        if request.devices_path:
            devices_path = Path(request.devices_path)
            if not devices_path.exists():
                raise HTTPException(status_code=404, detail=f"Devices config not found: {request.devices_path}")

        if request.confirm_real and request.mode != "real":
            raise HTTPException(
                status_code=400,
                detail="confirm_real=true is only valid in real mode",
            )

        if request.mode == "real" and not request.confirm_real:
            raise HTTPException(status_code=400, detail="Real mode requires confirm_real=true")

        if request.mode == "real":
            # Reject a manual light source up front: its terminal confirmation
            # prompt (input()) would hang the server thread. Web real mode needs
            # a pwm_modbus source with programmatic laser control.
            try:
                _, devices_config = load_workflow_and_devices(
                    request.config_path, devices_override=request.devices_path
                )
            except ConfigError as e:
                raise HTTPException(status_code=400, detail=f"Invalid configuration: {e}")
            if devices_config.light.type == "manual":
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Web API real mode requires a pwm_modbus light source; a manual light "
                        "needs terminal confirmation which would hang the server"
                    ),
                )

        # Create job
        job_id = task_queue.create_job("single_point")

        # Submit to queue
        await task_queue.submit_single_point(
            job_id=job_id,
            config_path=request.config_path,
            devices_path=request.devices_path,
            mode=request.mode,
            confirm_real=request.confirm_real,
        )

        job = task_queue.get_job(job_id)
        if not job:
            raise HTTPException(status_code=500, detail="Failed to create job")

        return job

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error starting single-point measurement")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


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
    job = task_queue.get_job(job_id)
    return {"status": job.status if job else "stopping", "job_id": job_id}


@router.websocket("/ws/jobs/{job_id}")
async def websocket_job_progress(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job progress updates."""
    await manager.connect(websocket, job_id)
    try:
        # Send initial job status
        job = task_queue.get_job(job_id)
        if job:
            await websocket.send_json({
                "type": "status",
                "status": job.status,
                "progress": job.progress.model_dump(),
            })

        # Keep connection alive and wait for messages
        while True:
            try:
                # Receive messages (for keepalive/ping)
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}")
    finally:
        await manager.disconnect(websocket, job_id)
