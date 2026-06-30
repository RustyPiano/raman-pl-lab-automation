"""Task queue for executing workflow jobs sequentially."""
import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from lab_auto.api.models import JobProgress, JobStatus
from lab_auto.api.websocket import manager
from lab_auto.config import load_workflow_and_devices
from lab_auto.devices.factory import DeviceFactory
from lab_auto.errors import ConfigError, DeviceError, SafetyError

logger = logging.getLogger(__name__)


class TaskQueue:
    """Single-threaded task queue for workflow execution.

    Ensures only one hardware operation runs at a time for safety.
    Uses a single-threaded executor to run blocking hardware operations
    without blocking the async event loop.
    """

    def __init__(self):
        self._jobs: dict[str, JobStatus] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._factory = DeviceFactory()
        # Single-threaded executor ensures hardware operations run sequentially
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hw-worker")

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
        """Request a job to stop (best-effort)."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in ("completed", "failed", "stopped"):
            return False

        # Update status to stopped (actual cancellation is best-effort)
        job.status = "stopped"
        job.completed_at = datetime.now(timezone.utc).isoformat()
        await manager.broadcast(job_id, {
            "type": "status",
            "status": "stopped",
            "message": "Job stop requested",
        })
        logger.info(f"Job {job_id} marked as stopped")
        return True

    async def _worker(self):
        """Background worker that processes jobs sequentially."""
        logger.info("Task queue worker running")
        while True:
            try:
                task = await self._queue.get()
                job_id = task["job_id"]

                job = self._jobs.get(job_id)
                if not job:
                    logger.error(f"Job {job_id} not found")
                    continue

                # Skip if job was already stopped
                if job.status == "stopped":
                    logger.info(f"Skipping stopped job {job_id}")
                    continue

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
                        )
                    else:
                        raise ValueError(f"Unknown job type: {task['type']}")

                    # Mark as completed
                    job.status = "completed"
                    job.completed_at = datetime.now(timezone.utc).isoformat()
                    await manager.broadcast(job_id, {
                        "type": "status",
                        "status": "completed",
                    })
                    logger.info(f"Job {job_id} completed successfully")

                except (ConfigError, DeviceError, SafetyError) as e:
                    job.status = "failed"
                    job.error = str(e)
                    job.completed_at = datetime.now(timezone.utc).isoformat()
                    await manager.broadcast(job_id, {
                        "type": "error",
                        "error": str(e),
                    })
                    logger.error(f"Job {job_id} failed: {e}")

                except Exception as e:
                    job.status = "failed"
                    job.error = f"Unexpected error: {str(e)}"
                    job.completed_at = datetime.now(timezone.utc).isoformat()
                    await manager.broadcast(job_id, {
                        "type": "error",
                        "error": f"Unexpected error: {str(e)}",
                    })
                    logger.exception(f"Job {job_id} failed with unexpected error")

                finally:
                    self._queue.task_done()

            except asyncio.CancelledError:
                logger.info("Worker task cancelled")
                break
            except Exception as e:
                logger.exception(f"Worker error: {e}")

    async def _execute_single_point(
        self,
        job_id: str,
        config_path: str,
        devices_path: str | None,
        mode: str,
        confirm_real: bool,
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
    ) -> dict[str, Any]:
        """Synchronous execution of single-point workflow.

        This runs in the single-threaded executor, ensuring hardware operations
        execute sequentially without blocking the async event loop.

        Note: This method cannot use asyncio.run() as it may be called from
        within an async context. Progress updates are handled by the caller.
        """
        if mode == "real" and not confirm_real:
            raise ConfigError("Real mode requires confirm_real=true")

        # Load configs
        workflow_config, devices_config = load_workflow_and_devices(
            config_path,
            devices_override=devices_path,
        )

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
            output_dir = workflow.run_single_point(require_confirmation=confirm_real)

            return {
                "output_directory": str(output_dir),
                "mode": mode,
            }
        finally:
            workflow.close()


# Global task queue instance
task_queue = TaskQueue()
