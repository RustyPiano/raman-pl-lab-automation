"""Task queue for executing workflow jobs sequentially."""
import asyncio
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from lab_auto.api.models import JobProgress, JobStatus
from lab_auto.api.websocket import manager
from lab_auto.config import load_workflow_and_devices
from lab_auto.devices.factory import DeviceFactory
from lab_auto.errors import ConfigError, DeviceError, SafetyError, WorkflowCancelled

_TERMINAL_STATES = ("completed", "failed", "stopped")

logger = logging.getLogger(__name__)


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

    def start(self):
        """Start the worker task."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())
            logger.info("Task queue worker started")

    async def stop(self):
        """Stop the worker task and shutdown executor."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Task queue worker stopped")

        # Shutdown executor gracefully
        self._executor.shutdown(wait=True)
        logger.info("Hardware worker thread pool shutdown")

    def create_job(self, job_type: str) -> str:
        """Create a new job and return its ID."""
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = JobStatus(
            id=job_id,
            type=job_type,
            status="pending",
            progress=JobProgress(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._cancel_events[job_id] = threading.Event()
        logger.info(f"Created job {job_id} of type {job_type}")
        return job_id

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
    ):
        """Submit a single-point measurement job."""
        if mode == "real" and not confirm_real:
            raise ConfigError("Real mode requires confirm_real=true")

        await self._queue.put({
            "job_id": job_id,
            "type": "single_point",
            "config_path": config_path,
            "devices_path": devices_path,
            "mode": mode,
            "confirm_real": confirm_real,
        })
        logger.info(f"Submitted single-point job {job_id} to queue")

    async def stop_job(self, job_id: str) -> bool:
        """Request a job to stop.

        A ``pending`` job is stopped immediately (the worker skips it on dequeue).
        A ``running``/``stopping`` job has its cancellation signal raised and moves
        to ``stopping``; it is only reported ``stopped`` once the workflow actually
        halts at a checkpoint (honest semantics — the laser may still be settling).
        """
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in _TERMINAL_STATES:
            return False

        event = self._cancel_events.get(job_id)
        if event is not None:
            event.set()

        if job.status == "pending":
            job.status = "stopped"
            job.completed_at = datetime.now(timezone.utc).isoformat()
            await manager.broadcast(job_id, {
                "type": "status",
                "status": "stopped",
                "message": "Job stopped before it started running",
            })
            logger.info(f"Pending job {job_id} marked as stopped")
            return True

        # Running (or already stopping): signal cancellation, don't claim it stopped
        # yet — the worker flips to 'stopped' when the workflow unwinds.
        job.status = "stopping"
        await manager.broadcast(job_id, {
            "type": "status",
            "status": "stopping",
            "message": "Stop requested; waiting for the workflow to halt safely",
        })
        logger.info(f"Job {job_id} stop requested; marked as stopping")
        return True

    def cancel_all(self) -> list[str]:
        """Signal cancellation for every unfinished job; return affected job ids.

        Sets the cancellation event on all non-terminal jobs and marks ``pending``
        jobs ``stopped`` directly (they never start). Running jobs stop cooperatively
        at their next checkpoint. Intended for an emergency-stop endpoint.
        """
        affected: list[str] = []
        for job_id, job in self._jobs.items():
            if job.status in _TERMINAL_STATES:
                continue
            event = self._cancel_events.get(job_id)
            if event is not None:
                event.set()
            if job.status == "pending":
                job.status = "stopped"
                job.completed_at = datetime.now(timezone.utc).isoformat()
            affected.append(job_id)
        if affected:
            logger.info(f"cancel_all signalled {len(affected)} job(s): {affected}")
        return affected

    def is_hardware_busy(self) -> bool:
        """True while the hardware worker is processing a job.

        Device endpoints (light status/off, scan) use this to avoid opening a
        second connection on the same serial port a running job is using.
        """
        return self._active_job_id is not None

    async def _worker(self):
        """Background worker that processes jobs sequentially.

        Every dequeued task calls ``task_done()`` exactly once (task/finally), and
        any unexpected error still marks the job failed instead of leaving it stuck
        in ``running`` — no job silently vanishes.
        """
        logger.info("Task queue worker running")
        while True:
            try:
                task = await self._queue.get()
            except asyncio.CancelledError:
                logger.info("Worker task cancelled")
                break
            try:
                await self._process_task(task)
            except asyncio.CancelledError:
                logger.info("Worker task cancelled")
                break
            except Exception as e:
                # Top-level guard: a bug outside the per-job handler must still fail
                # the job (not leave it 'running' forever) and be reported.
                await self._fail_job(task.get("job_id"), f"Unexpected error: {str(e)}")
                logger.exception(f"Worker error processing task: {e}")
            finally:
                self._queue.task_done()

    async def _fail_job(self, job_id: str | None, error: str) -> None:
        """Mark a job failed and broadcast the error, if it isn't already terminal."""
        job = self._jobs.get(job_id) if job_id else None
        if job is None or job.status in _TERMINAL_STATES:
            return
        job.status = "failed"
        job.error = error
        job.completed_at = datetime.now(timezone.utc).isoformat()
        await manager.broadcast(job_id, {"type": "error", "error": error})

    async def _process_task(self, task: dict[str, Any]) -> None:
        """Run a single dequeued task through its lifecycle."""
        job_id = task["job_id"]
        job = self._jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # Skip if the job was stopped while still pending in the queue.
        if job.status == "stopped":
            logger.info(f"Skipping stopped job {job_id}")
            return

        cancel_event = self._cancel_events.get(job_id)

        # Track which job the hardware executor is working on so device
        # endpoints can detect a busy port instead of racing it (see
        # is_hardware_busy). Set for the whole processing lifetime, cleared
        # unconditionally in `finally` regardless of which branch below exits.
        self._active_job_id = job_id
        try:

            # Update to running
            job.status = "running"
            job.started_at = datetime.now(timezone.utc).isoformat()
            await manager.broadcast(job_id, {
                "type": "status",
                "status": "running",
            })

            try:
                if task["type"] == "single_point":
                    await self._execute_single_point(
                        job_id,
                        task["config_path"],
                        task["devices_path"],
                        task["mode"],
                        task["confirm_real"],
                        cancel_event,
                    )
                else:
                    raise ValueError(f"Unknown job type: {task['type']}")

            except WorkflowCancelled:
                # Cooperative stop reached a checkpoint and unwound cleanly.
                job.status = "stopped"
                job.completed_at = datetime.now(timezone.utc).isoformat()
                await manager.broadcast(job_id, {
                    "type": "status",
                    "status": "stopped",
                    "message": "Job stopped",
                })
                logger.info(f"Job {job_id} stopped by cancellation")
                return

            except (ConfigError, DeviceError, SafetyError) as e:
                job.status = "failed"
                job.error = str(e)
                job.completed_at = datetime.now(timezone.utc).isoformat()
                await manager.broadcast(job_id, {
                    "type": "error",
                    "error": str(e),
                })
                logger.error(f"Job {job_id} failed: {e}")
                return

            except Exception as e:
                job.status = "failed"
                job.error = f"Unexpected error: {str(e)}"
                job.completed_at = datetime.now(timezone.utc).isoformat()
                await manager.broadcast(job_id, {
                    "type": "error",
                    "error": f"Unexpected error: {str(e)}",
                })
                logger.exception(f"Job {job_id} failed with unexpected error")
                return

            # Natural completion. Only write a terminal state if we're still mid-flight
            # (guards against a racing stop that already set a terminal state).
            if job.status not in ("running", "stopping"):
                return
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc).isoformat()
            # If a stop was requested but the workflow finished first, say so honestly.
            message = (
                "completed before stop request took effect"
                if cancel_event is not None and cancel_event.is_set()
                else None
            )
            await manager.broadcast(job_id, {
                "type": "status",
                "status": "completed",
                "message": message,
            })
            logger.info(f"Job {job_id} completed successfully")
        finally:
            self._active_job_id = None

    async def _execute_single_point(
        self,
        job_id: str,
        config_path: str,
        devices_path: str | None,
        mode: str,
        confirm_real: bool,
        cancel_event: threading.Event | None = None,
    ):
        """Execute a single-point measurement in a thread pool.

        Runs blocking hardware operations in the single-threaded executor
        to maintain hardware safety without blocking the async event loop.
        """
        job = self._jobs[job_id]

        # Progress callback
        async def broadcast_progress(step: str, completed: int, total: int, message: str | None = None):
            job.progress.current_step = step
            job.progress.completed_steps = completed
            job.progress.total_steps = total
            job.progress.message = message
            if total > 0:
                job.progress.percentage = (completed / total) * 100.0

            await manager.broadcast(job_id, {
                "type": "progress",
                "step": step,
                "completed": completed,
                "total": total,
                "message": message,
                "percentage": job.progress.percentage,
            })

        # Send initial progress
        await broadcast_progress("initializing", 0, 10, "Loading configuration")

        # Run in thread pool to avoid blocking async loop
        # Use the single-threaded executor to ensure sequential hardware access
        loop = asyncio.get_event_loop()

        await broadcast_progress("executing", 2, 10, "Running single-point measurement")

        result = await loop.run_in_executor(
            self._executor,  # Use our single-threaded executor
            self._run_single_point_sync,
            config_path,
            devices_path,
            mode,
            confirm_real,
            job_id,
            cancel_event,
        )

        await broadcast_progress("saving", 9, 10, "Saving results")

        job.result = result
        await broadcast_progress("completed", 10, 10, "Measurement completed")

    def _run_single_point_sync(
        self,
        config_path: str,
        devices_path: str | None,
        mode: str,
        confirm_real: bool,
        job_id: str,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        """Synchronous execution of single-point workflow.

        This runs in the single-threaded executor, ensuring hardware operations
        execute sequentially without blocking the async event loop.

        Note: This method cannot use asyncio.run() as it may be called from
        within an async context. Progress updates are handled by the caller.
        """
        # Defense-in-depth: re-reject the same dangerous combinations the router
        # guards, so a caller bypassing the router can't queue an unsafe run.
        if mode == "real" and not confirm_real:
            raise ConfigError("Real mode requires confirm_real=true")
        if confirm_real and mode != "real":
            raise ConfigError("confirm_real=true is only valid in real mode")

        # Load configs
        workflow_config, devices_config = load_workflow_and_devices(
            config_path,
            devices_override=devices_path,
        )

        if mode == "real" and getattr(getattr(devices_config, "light", None), "type", None) == "manual":
            raise ConfigError(
                "Web API real mode requires a pwm_modbus light source; a manual light needs "
                "terminal confirmation which would hang the server"
            )

        should_cancel = (lambda: cancel_event.is_set()) if cancel_event is not None else None

        # Create workflow based on mode
        if mode == "dry_run":
            from lab_auto.workflow.raman import RamanWorkflow
            workflow = RamanWorkflow.dry_run(workflow_config)
        elif mode == "simulated":
            from lab_auto.workflow.raman import RamanWorkflow
            workflow = RamanWorkflow.simulated(workflow_config)
        elif mode == "real":
            workflow = self._factory.create_single_point_workflow(
                workflow_config,
                devices_config,
            )
        else:
            raise ValueError(f"Invalid mode: {mode}")

        try:
            # Execute workflow (blocking hardware operation)
            output_dir = workflow.run_single_point(
                require_confirmation=confirm_real,
                should_cancel=should_cancel,
            )

            return {
                "output_directory": str(output_dir),
                "mode": mode,
            }
        finally:
            workflow.close()


# Global task queue instance
task_queue = TaskQueue()
