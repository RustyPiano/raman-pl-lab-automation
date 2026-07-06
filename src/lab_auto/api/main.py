"""FastAPI main application entry point."""
import asyncio
import atexit
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from lab_auto.api.models import HealthResponse
from lab_auto.api.routers import configs, devices, system, workflow
from lab_auto.api.task_queue import task_queue
from lab_auto.config import load_devices_config
from lab_auto.devices.factory import DeviceFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Mirrors the devices_config default used throughout routers/devices.py. A
# dev machine with no real rig attached simply won't have this file, which is
# the normal/expected case for _reset_light_best_effort below.
_DEFAULT_DEVICES_CONFIG = Path("configs/devices.yaml")


def _reset_light_best_effort() -> tuple[bool, str]:
    """Try to force a configured pwm_modbus light off; never raises.

    Shared by the startup reset, the graceful-shutdown reset, and the atexit
    safety net below -- all three want exactly the same action: create the
    light (DeviceFactory.create_light's default initial_all_off=True already
    performs the all-channels-off + read-back reset), then drop the
    connection without touching a channel again.

    Returns ``(success, detail)`` so each call site can log with its own
    context. ``success`` is True both when the reset genuinely confirmed all
    channels off AND when there was nothing to reset (no default devices
    config file, or a non-pwm_modbus light) -- neither is a failure worth
    warning about.
    """
    try:
        if not _DEFAULT_DEVICES_CONFIG.exists():
            return True, "no default devices config present; nothing to reset"
        config = load_devices_config(_DEFAULT_DEVICES_CONFIG)
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
    # Startup
    logger.info("Starting FastAPI application")
    # Power-on safety reset: a previous crash may have left a channel
    # (possibly the laser) energized, and this fresh process has no idea.
    # Run off the event loop -- it does real serial IO -- and never let a
    # failure here block the API from starting (no hardware attached is the
    # normal case on a dev machine).
    loop = asyncio.get_event_loop()
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
    allow_origins=[
        "http://localhost:5173",  # Vite default
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(devices.router)
app.include_router(configs.router)
app.include_router(workflow.router)
app.include_router(system.router)

# Static file serving (for production frontend)
dist_path = Path(__file__).parent.parent.parent.parent / "dist"
if dist_path.exists():
    app.mount("/", StaticFiles(directory=str(dist_path), html=True), name="static")
    logger.info(f"Mounted static files from {dist_path}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/health", response_model=HealthResponse)
async def api_health_check():
    """API health check endpoint."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "lab_auto.api.main:app",
        host="127.0.0.1",
        port=8008,
        reload=True,
        log_level="info",
    )
