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
from pathlib import Path

from fastapi import APIRouter

from lab_auto.api.task_queue import task_queue
from lab_auto.config import load_devices_config
from lab_auto.devices.factory import DeviceFactory
from lab_auto.errors import ConfigError, DeviceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["system"])

_LASER_OFF_TIMEOUT_S = 15


@router.post("/emergency-stop")
async def emergency_stop(devices_config: str = "configs/devices.yaml"):
    """Cancel every running job and force the light off, best-effort.

    Two independent actions, both best-effort:

    1. ``task_queue.cancel_all()`` -- signals every non-terminal job to stop.
       This is cooperative: a job stuck in a blocking hardware call may not
       observe it immediately.
    2. Force the PWM light off. This deliberately does NOT go through the
       task queue's single-threaded hardware executor -- that executor may be
       exactly what's wedged, which is why an emergency stop was needed in
       the first place. Instead it opens its own short-lived connection to
       the light controller in the default thread pool.

    This never raises a 500 for a failed laser-off: the operator needs a
    response even when the news is bad, and the response says so plainly
    (``laser_off`` is ``"failed: <reason>"``) so they know to use the
    physical switch immediately instead of trusting a request that hung or
    errored.
    """
    cancelled_jobs = task_queue.cancel_all()

    config_path = Path(devices_config)
    if not config_path.exists():
        # Nothing configured to act on -- honest "not applicable", not a
        # failure (there may be no PWM light on this deployment at all).
        return {"jobs_cancelled": cancelled_jobs, "laser_off": "not_applicable"}

    try:
        config = load_devices_config(config_path)
    except (ConfigError, DeviceError) as e:
        return {
            "jobs_cancelled": cancelled_jobs,
            "laser_off": f"failed: could not load devices config: {e}",
            "message": "Software could not confirm the laser is off. Use the physical switch immediately.",
        }

    if config.light.type != "pwm_modbus":
        return {"jobs_cancelled": cancelled_jobs, "laser_off": "not_applicable"}

    def _force_off():
        factory = DeviceFactory()
        light = factory.create_light(config, initial_all_off=False)
        try:
            light.safety_reset()
        finally:
            light.close(all_off=False)

    try:
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(loop.run_in_executor(None, _force_off), timeout=_LASER_OFF_TIMEOUT_S)
        return {"jobs_cancelled": cancelled_jobs, "laser_off": "confirmed"}
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
