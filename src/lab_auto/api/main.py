"""FastAPI main application entry point."""
import asyncio
import atexit
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from lab_auto.api.models import HealthResponse
from lab_auto.api.paths import default_devices_config_path, job_state_path
from lab_auto.api.routers import configs, devices, history, system, workflow
from lab_auto.api.task_queue import task_queue
from lab_auto.config import load_devices_config
from lab_auto.devices.factory import DeviceFactory
from lab_auto.errors import ConfigError, HardwareBusyError, LabAutomationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
_atexit_reset_armed = False


def _reset_light_best_effort(config_path: Path | None = None) -> tuple[bool, str]:
    """Try to force a configured pwm_modbus light off; never raises.

    Shared by the startup reset, the graceful-shutdown reset, and the atexit
    safety net below -- all three want exactly the same action: create the
    light (DeviceFactory.create_light's default initial_all_off=True already
    performs the all-channels-off + read-back reset), then drop the
    connection without touching a channel again.

    Returns ``(success, detail)`` so each call site can log with its own context.
    """
    try:
        config_path = config_path or task_queue.safety_devices_path() or default_devices_config_path()
        if not config_path.exists():
            return False, f"devices config not found: {config_path}"
        config = load_devices_config(config_path)
        if config.light.type != "pwm_modbus":
            return True, f"light type '{config.light.type}' has no hardware to reset"
        factory = DeviceFactory()
        light = factory.create_light(config)  # initial_all_off=True (default) does the reset
        light.close(all_off=False)  # already confirmed off; just drop the port
        return True, "power-on laser safety reset confirmed"
    except Exception as e:  # noqa: BLE001 - this is the last-resort safety net, it must not raise
        return False, str(e)


def _atexit_safety_reset() -> None:
    """Best-effort synchronous safety net for normal interpreter exit.

    Registered with atexit so an uncaught exception, Ctrl-C, or sys.exit()
    still gets one more attempt at forcing the laser off before the process
    dies. This CANNOT run on SIGKILL (`kill -9`) -- nothing in-process runs
    on that signal -- which is exactly why the startup reset exists: the
    next boot re-asserts the safe state regardless of how the previous
    process died. No asyncio here: atexit handlers run synchronously and the
    event loop may already be gone.
    """
    if not _atexit_reset_armed:
        return
    try:
        success, detail = _reset_light_best_effort()
        if success:
            logger.info(f"atexit safety reset: {detail}")
        else:
            logger.warning(f"atexit safety reset FAILED: {detail}")
    except Exception:  # noqa: BLE001 - must never block interpreter exit
        pass


atexit.register(_atexit_safety_reset)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _atexit_reset_armed
    _atexit_reset_armed = True
    # Startup
    logger.info("Starting FastAPI application")
    recovery_error = None
    try:
        task_queue.restore_jobs(job_state_path())
    except (ConfigError, OSError) as exc:
        recovery_error = exc  # still attempt the safety reset before refusing startup
    # Power-on safety reset: a previous crash may have left a channel
    # (possibly the laser) energized, and this fresh process has no idea.
    # Run off the event loop -- it does real serial IO -- and never let a
    # failure here block the API from starting (no hardware attached is the
    # normal case on a dev machine).
    loop = asyncio.get_running_loop()
    success, detail = await loop.run_in_executor(None, _reset_light_best_effort)
    if success:
        logger.info(f"Startup safety reset: {detail}")
    else:
        logger.warning(
            "STARTUP SAFETY RESET FAILED (%s). On real hardware this means the API "
            "cannot confirm the laser is off after this restart -- check the light "
            "controller / physical switch before running anything.",
            detail,
        )
    if recovery_error is not None:
        raise recovery_error
    task_queue.start()
    logger.info("Task queue worker started")

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application")
    await task_queue.stop()
    logger.info("Task queue worker stopped")
    # Same best-effort reset on graceful shutdown (uvicorn SIGTERM handling
    # runs this lifespan shutdown path). The atexit handler above is the
    # backstop for exits that never reach here.
    success, detail = await loop.run_in_executor(None, _reset_light_best_effort)
    if success:
        logger.info(f"Shutdown safety reset: {detail}")
    else:
        logger.warning(f"Shutdown safety reset FAILED: {detail}")
    _atexit_reset_armed = False


# Create FastAPI app
app = FastAPI(
    title="Raman/PL Lab Automation API",
    description="REST API and WebSocket interface for autonomous Raman/PL measurement platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration for Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(devices.router)
app.include_router(configs.router)
app.include_router(workflow.router)
app.include_router(history.router)
app.include_router(system.router)


# 路由内不再逐个捕获：配置/设备/安全错误统一返回 400，硬件忙返回 409，硬件调用超时返回 504
@app.exception_handler(LabAutomationError)
async def lab_error_handler(request: Request, exc: LabAutomationError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(HardwareBusyError)
async def hardware_busy_handler(request: Request, exc: HardwareBusyError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(TimeoutError)
async def timeout_handler(request: Request, exc: TimeoutError):
    return JSONResponse(status_code=504, content={"detail": "Hardware call timed out"})


@app.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """API health check endpoint."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# Production frontend. API and health routes above stay ahead of the SPA
# fallback, while direct navigation to a client route still serves index.html.
dist_path = Path(__file__).resolve().parents[3] / "frontend" / "dist"
if dist_path.exists():
    assets_path = dist_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    @app.get("/", include_in_schema=False)
    async def frontend_index():
        return FileResponse(dist_path / "index.html")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    async def frontend_fallback(frontend_path: str):
        if frontend_path == "api" or frontend_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (dist_path / frontend_path).resolve()
        if candidate.is_relative_to(dist_path) and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist_path / "index.html")

    logger.info(f"Mounted static files from {dist_path}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "lab_auto.api.main:app",
        host="127.0.0.1",
        port=8008,
        log_level="info",
    )
