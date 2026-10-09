"""Task queue for executing workflow jobs sequentially."""
import asyncio
import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lab_auto.api.models import JobProgress, JobStatus
from lab_auto.api.websocket import manager
from lab_auto.config import load_workflow_and_devices
from lab_auto.devices.factory import DeviceFactory
from lab_auto.devices.light import PwmModbusLight
from lab_auto.errors import ConfigError, HardwareBusyError, LabAutomationError, WorkflowCancelled
from lab_auto.storage import write_json
from lab_auto.workflow.raman import RamanWorkflow, read_single_point_result

_TERMINAL_STATES = ("completed", "failed", "stopped")
_MAX_JOB_HISTORY = 100

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskQueue:
    """Single-threaded task queue for workflow execution.

    Ensures only one hardware operation runs at a time for safety.
    Uses a single-threaded executor to run blocking hardware operations
    without blocking the async event loop.
    """

    def __init__(self):
        self._jobs: dict[str, JobStatus] = {}
        # Per-job cooperative cancellation signals, read by the workflow running in
        # the hardware thread via a should_cancel callback.
        self._cancel_events: dict[str, threading.Event] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._factory = DeviceFactory()
        # Single-threaded executor ensures hardware operations run sequentially
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hw-worker")
        # Job the hardware worker is currently processing, if any. See
        # is_hardware_busy() and _process_task().
        self._active_job_id: str | None = None
        self._active_devices_path: Path | None = None
        self._last_devices_path: Path | None = None
        self._active_light: object | None = None
        self._device_operations: set[asyncio.Future] = set()
        self._state_path: Path | None = None

    def restore_jobs(self, path: Path) -> None:
        """Recover records, never replay hardware commands after a restart."""
        self._state_path = path
        self._jobs = {}
        self._cancel_events = {}
        self._last_devices_path = None
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            jobs = [JobStatus.model_validate(item) for item in data["jobs"]]
            last_devices = data.get("last_devices_path")
            last_devices = Path(last_devices) if last_devices is not None else None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ConfigError(f"Cannot recover task records from {path}: {exc}") from exc
        self._jobs = {job.id: job for job in jobs}
        self._cancel_events = {job.id: threading.Event() for job in jobs}
        self._last_devices_path = last_devices
        for job in jobs:
            if job.status not in _TERMINAL_STATES:
                job.status = "failed"
                job.error = "Server restarted before completion; hardware state must be checked before a new run"
                job.completed_at = _now()
        self._save_jobs()

    def _save_jobs(self) -> None:
        if self._state_path is not None:
            write_json(self._state_path, {
                "last_devices_path": self._last_devices_path,
                "jobs": [job.model_dump(mode="json") for job in self._jobs.values()],
            })

    def _save_cancelled_jobs(self) -> None:
        # Emergency OFF has already been dispatched before this callback runs.
        try:
            self._save_jobs()
        except OSError:
            logger.exception("Could not persist cancellation; hardware cancellation is still active")

    def start(self):
        """Start the worker task."""
        if self._worker_task is None or self._worker_task.done():
            if self._executor._shutdown:
                self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hw-worker")
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("Task queue worker started")

    async def stop(self):
        """Stop the worker task and shutdown executor."""
        await self.cancel_all()
        if self._active_light is not None:
            try:
                loop = asyncio.get_running_loop()
                await asyncio.wait_for(loop.run_in_executor(None, self.force_active_light_off), timeout=15)
            except Exception as exc:  # noqa: BLE001 - shutdown must continue to close every device
                logger.error("Failed to force active light off during shutdown: %s", exc)
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Task queue worker stopped")

        # Do not block the event loop while a native call finishes unwinding.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._executor.shutdown, True)
        logger.info("Hardware worker thread pool shutdown")

    def create_job(self, job_type: str) -> str:
        """Create a new job and return its ID."""
        self._prune_jobs()
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = JobStatus(
            id=job_id,
            type=job_type,
            status="pending",
            progress=JobProgress(),
            created_at=_now(),
        )
        self._cancel_events[job_id] = threading.Event()
        self._save_jobs()
        logger.info(f"Created job {job_id} of type {job_type}")
        return job_id

    def _prune_jobs(self) -> None:
        while len(self._jobs) >= _MAX_JOB_HISTORY:
            oldest_terminal = next(
                (job_id for job_id, job in self._jobs.items() if job.status in _TERMINAL_STATES),
                None,
            )
            if oldest_terminal is None:
                return
            self._jobs.pop(oldest_terminal)
            self._cancel_events.pop(oldest_terminal)

    def get_job(self, job_id: str) -> JobStatus | None:
        """Get job status by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobStatus]:
        """List all jobs."""
        return list(self._jobs.values())

    async def submit_single_point(
        self,
        job_id: str,
        config_path: str,
        devices_path: str | None,
        mode: str,
        confirm_real: bool = False,
        sample_id: str | None = None,
        operator: str | None = None,
        subtract_background: bool | None = None,
    ):
        """Queue a single-point measurement already validated by the router."""
        self._jobs[job_id].mode = mode
        self._save_jobs()
        await self._queue.put({
            "job_id": job_id,
            "config_path": config_path,
            "devices_path": devices_path,
            "mode": mode,
            "confirm_real": confirm_real,
            "sample_id": sample_id,
            "operator": operator,
            "subtract_background": subtract_background,
        })
        logger.info(f"Submitted single-point job {job_id} to queue")

    def _signal_stop(self, job_id: str, running_message: str) -> dict[str, Any]:
        """Raise the job's cancel signal and return the status message to publish.

        A ``pending`` job is stopped immediately (the worker skips it on dequeue).
        A ``running``/``stopping`` job moves to ``stopping``; it is only reported
        ``stopped`` once the workflow actually halts at a checkpoint (honest
        semantics — the laser may still be settling).
        """
        job = self._jobs[job_id]
        self._cancel_events[job_id].set()
        if job.status == "pending":
            job.status = "stopped"
            job.completed_at = _now()
            message = "任务开始前已停止"
        else:
            job.status = "stopping"
            message = running_message
        return {"type": "status", "status": job.status, "message": message}

    async def stop_job(self, job_id: str) -> bool:
        """Request a job to stop; False if it is unknown or already finished."""
        job = self._jobs.get(job_id)
        if job is None or job.status in _TERMINAL_STATES:
            return False
        message = self._signal_stop(job_id, "已请求停止，关闭激光后结束")
        self._save_jobs()
        await manager.broadcast(job_id, message)
        logger.info(f"Job {job_id} stop requested; now {job.status}")
        return True

    async def cancel_all(self) -> list[str]:
        """Signal cancellation for every unfinished job; return affected job ids.

        Notifications are fire-and-forget and persistence is deferred so neither
        can delay the emergency light-off that follows.
        """
        affected = [job_id for job_id, job in self._jobs.items() if job.status not in _TERMINAL_STATES]
        for job_id in affected:
            manager.notify(job_id, self._signal_stop(job_id, "急停：关闭激光后结束"))
        if affected:
            asyncio.get_running_loop().call_soon(self._save_cancelled_jobs)
            logger.info(f"cancel_all signalled {len(affected)} job(s): {affected}")
        return affected

    def is_hardware_busy(self) -> bool:
        """True while the hardware worker is processing a job.

        Device endpoints (light status/off, scan) use this to avoid opening a
        second connection on the same serial port a running job is using.
        """
        return self._active_job_id is not None or any(not future.done() for future in self._device_operations)

    async def run_device_operation(self, fn, *, require_idle: bool = True):
        """Share the workflow executor; timed-out HTTP callers do not release hardware."""
        if require_idle and self.is_hardware_busy():
            raise HardwareBusyError("任务或设备操作正在使用硬件，请稍后重试")
        future = asyncio.get_running_loop().run_in_executor(self._executor, fn)
        self._device_operations.add(future)
        future.add_done_callback(self._device_operation_done)
        return await asyncio.shield(future)

    def _device_operation_done(self, future) -> None:
        self._device_operations.discard(future)
        if not future.cancelled() and future.exception() is not None:
            logger.error("Device operation failed: %s", future.exception())

    def safety_devices_path(self) -> Path | None:
        """Actual devices config for the active or most recent hardware job."""
        return self._active_devices_path or self._last_devices_path

    def force_active_light_off(self) -> bool:
        """Use the active workflow's already-open light handle for emergency OFF.

        Only a PWM light can be switched off by software; a manual light (or no
        active job) returns False so the caller falls back to the configured light.
        """
        light = self._active_light
        if not isinstance(light, PwmModbusLight):
            return False
        light.emergency_off()
        return True

    async def _worker(self):
        """Background worker that processes jobs sequentially.

        Every dequeued task calls ``task_done()`` exactly once, and an error
        outside the per-job handler still fails the job instead of leaving it
        stuck in ``running``.
        """
        logger.info("Task queue worker running")
        while True:
            task = await self._queue.get()
            try:
                await self._process_task(task)
            except Exception as e:
                logger.exception(f"Worker error processing task: {e}")
                await self._fail_job(task["job_id"], f"Unexpected error: {e}")
            finally:
                self._queue.task_done()

    async def _fail_job(self, job_id: str, error: str) -> None:
        """Mark a job failed and broadcast the error, if it isn't already terminal."""
        job = self._jobs.get(job_id)
        if job is None or job.status in _TERMINAL_STATES:
            return
        job.status = "failed"
        job.error = error
        job.completed_at = _now()
        self._save_jobs()
        await manager.broadcast(job_id, {"type": "error", "error": error})

    async def _process_task(self, task: dict[str, Any]) -> None:
        """Run a single dequeued task through its lifecycle."""
        job_id = task["job_id"]
        job = self._jobs.get(job_id)
        # A job stopped while pending may already be pruned or marked stopped.
        if job is None or job.status == "stopped":
            return

        # Track which job the hardware executor is working on so device
        # endpoints can detect a busy port instead of racing it (see
        # is_hardware_busy). Cleared unconditionally in `finally`.
        self._active_job_id = job_id
        try:
            job.status = "running"
            job.started_at = _now()
            job.progress = JobProgress(current_step="executing", percentage=0.0, message="正在测量")
            self._save_jobs()
            await manager.broadcast(job_id, {
                "type": "status",
                "status": "running",
                "message": job.progress.message,
                "progress": job.progress.model_dump(),
            })

            try:
                await self._execute_single_point(job_id, task)
            except WorkflowCancelled:
                # Cooperative stop reached a checkpoint and unwound cleanly.
                job.status = "stopped"
                job.completed_at = _now()
                self._save_jobs()
                await manager.broadcast(job_id, {"type": "status", "status": "stopped", "message": "任务已停止"})
                logger.info(f"Job {job_id} stopped by cancellation")
                return
            except Exception as e:
                logger.exception(f"Job {job_id} failed")
                await self._fail_job(job_id, str(e) if isinstance(e, LabAutomationError) else f"Unexpected error: {e}")
                return

            # Natural completion. Only write a terminal state if we're still mid-flight
            # (guards against a racing stop that already set a terminal state).
            if job.status not in ("running", "stopping"):
                return
            job.status = "completed"
            job.completed_at = _now()
            # If a stop was requested but the workflow finished first, say so.
            message = "停止请求生效前任务已完成" if self._cancel_events[job_id].is_set() else "测量完成"
            job.progress = JobProgress(current_step="completed", percentage=100.0, message=message)
            self._save_jobs()
            await manager.broadcast(job_id, {
                "type": "status",
                "status": "completed",
                "message": message,
                "progress": job.progress.model_dump(),
                "result": job.result,
            })
            logger.info(f"Job {job_id} completed successfully")
        finally:
            self._active_job_id = None

    async def _execute_single_point(self, job_id: str, task: dict[str, Any]):
        """Run the blocking measurement on the single hardware executor."""
        if task["mode"] == "real" and task["devices_path"] is not None:
            self._last_devices_path = Path(task["devices_path"]).resolve()
            self._save_jobs()
        loop = asyncio.get_running_loop()
        self._jobs[job_id].result = await loop.run_in_executor(
            self._executor, self._run_single_point_sync, task, self._cancel_events[job_id]
        )

    def _run_single_point_sync(self, task: dict[str, Any], cancel_event: threading.Event) -> dict[str, Any]:
        """Synchronous single-point workflow, executed on the hardware thread."""
        mode = task["mode"]
        workflow_config, devices_config = load_workflow_and_devices(
            task["config_path"],
            devices_override=task["devices_path"],
        )
        actual_devices_path = Path(task["devices_path"] or workflow_config.devices_config).resolve()
        if mode == "real":
            self._last_devices_path = actual_devices_path

        sample = workflow_config.sample
        if task.get("sample_id") is not None:
            sample = replace(sample, id=task["sample_id"])
        if task.get("operator") is not None:
            sample = replace(sample, operator=task["operator"])
        workflow_config = replace(workflow_config, sample=sample)
        if task.get("subtract_background") is not None:
            workflow_config = replace(
                workflow_config,
                acquisition=replace(workflow_config.acquisition, subtract_background=task["subtract_background"]),
            )

        if mode == "dry_run":
            workflow = RamanWorkflow.dry_run(workflow_config)
        elif mode == "simulated":
            workflow = RamanWorkflow.simulated(workflow_config)
        else:
            workflow = self._factory.create_single_point_workflow(workflow_config, devices_config)

        if mode != "real":
            workflow.devices_snapshot = asdict(devices_config)
        self._active_devices_path = actual_devices_path if mode == "real" else None
        self._active_light = workflow.light
        try:
            output_dir = workflow.run_single_point(
                require_confirmation=task["confirm_real"],
                should_cancel=cancel_event.is_set,
            )
            return {
                "output_directory": str(output_dir),
                "mode": mode,
                **read_single_point_result(output_dir),
            }
        finally:
            try:
                workflow.close()
            finally:
                self._active_light = None
                self._active_devices_path = None


# Global task queue instance
task_queue = TaskQueue()
