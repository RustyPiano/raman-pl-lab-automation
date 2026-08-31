"""System-level safety endpoints (software emergency stop).

This is a BEST-EFFORT software emergency stop. It is not, and cannot be, a
substitute for a physical emergency-stop button or breaker: it depends on the
process being alive, the event loop being responsive, and the light
controller's serial port being reachable. If any of those are true a
determined failure has probably already made a physical stop necessary
anyway. Treat this endpoint as a fast, best-effort first response -- the
physical switch is the final backstop.
"""
import asyncio
import logging
from fastapi import APIRouter

from lab_auto.api.paths import default_devices_config_path
from lab_auto.api.task_queue import task_queue
from lab_auto.config import load_devices_config
from lab_auto.devices.factory import DeviceFactory
from lab_auto.errors import ConfigError, DeviceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["system"])

_LASER_OFF_TIMEOUT_S = 15


@router.post("/emergency-stop")
async def emergency_stop():
    """Cancel every running job and force the light off, best-effort.

    Two independent actions, both best-effort:

    1. ``task_queue.cancel_all()`` -- signals every non-terminal job to stop.
       This is cooperative: a job stuck in a blocking hardware call may not
       observe it immediately.
    2. Force the PWM light off outside the hardware executor. It first reuses
       the active workflow's serial handle; if none exists, it opens a short-lived
       connection using the active/last server-owned devices configuration.

    This never raises a 500 for a failed laser-off: the operator needs a
    response even when the news is bad, and the response says so plainly
    (``laser_off`` is ``"failed: <reason>"``) so they know to use the
    physical switch immediately instead of trusting a request that hung or
    errored.
    """
    cancelled_jobs = await task_queue.cancel_all()

    def _force_off():
        if task_queue.force_active_light_off():
            return "confirmed"
        config_path = task_queue.safety_devices_path() or default_devices_config_path()
        if not config_path.exists():
            raise ConfigError(f"devices config not found: {config_path}")
        config = load_devices_config(config_path)
        if config.light.type != "pwm_modbus":
            return "not_applicable"
        factory = DeviceFactory()
        light = factory.create_light(config, initial_all_off=False)
        try:
            light.safety_reset()
        finally:
            light.close(all_off=False)
        return "confirmed"

    try:
        loop = asyncio.get_running_loop()
        laser_off = await asyncio.wait_for(loop.run_in_executor(None, _force_off), timeout=_LASER_OFF_TIMEOUT_S)
        return {"jobs_cancelled": cancelled_jobs, "laser_off": laser_off}
    except asyncio.TimeoutError:
        logger.error("Emergency stop: timed out attempting to force the light off")
        return {
            "jobs_cancelled": cancelled_jobs,
            "laser_off": "failed: timed out reaching the light controller",
            "message": "Software could not confirm the laser is off. Use the physical switch immediately.",
        }
    except Exception as e:  # noqa: BLE001 - an emergency stop must never itself 500
        logger.exception("Emergency stop: failed to force the light off")
        return {
            "jobs_cancelled": cancelled_jobs,
            "laser_off": f"failed: {e}",
            "message": "Software could not confirm the laser is off. Use the physical switch immediately.",
        }
