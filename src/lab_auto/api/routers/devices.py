"""Device management API endpoints."""
import asyncio
import logging
from fastapi import APIRouter, HTTPException

from lab_auto.api.models import DeviceStatusResponse, LightStatusResponse
from lab_auto.api.paths import default_devices_config_path
from lab_auto.api.task_queue import task_queue
from lab_auto.config import load_devices_config
from lab_auto.devices.factory import DeviceFactory
from lab_auto.errors import ConfigError, DeviceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/devices", tags=["devices"])

# Every blocking hardware call below runs in the process-wide default executor
# (asyncio.get_event_loop().run_in_executor(None, ...)) -- deliberately NOT the
# task queue's single-threaded hardware executor, which a running job may be
# occupying. That is exactly the case task_queue.is_hardware_busy() exists to
# detect and refuse up front instead of racing the same serial port. Bounded
# by this timeout so a wedged port fails the HTTP request instead of hanging
# it indefinitely.
_HARDWARE_CALL_TIMEOUT_S = 15


async def _run_in_thread(fn):
    """Run a blocking hardware call off the event loop, with a bounded wait."""
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(loop.run_in_executor(None, fn), timeout=_HARDWARE_CALL_TIMEOUT_S)


@router.get("/status", response_model=DeviceStatusResponse)
async def get_device_status():
    """Get status of all devices."""
    if task_queue.is_hardware_busy():
        raise HTTPException(status_code=409, detail="任务正在使用硬件，无法查询设备状态")
    try:
        config = load_devices_config(default_devices_config_path())

        def _run():
            factory = DeviceFactory()
            return factory.run_status(config)

        status = await _run_in_thread(_run)
        return DeviceStatusResponse(**status)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Device status query timed out")
    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error getting device status")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/scan")
async def scan_devices():
    """Scan for available devices."""
    if task_queue.is_hardware_busy():
        raise HTTPException(status_code=409, detail="任务正在使用硬件，无法执行设备扫描")
    try:
        config = load_devices_config(default_devices_config_path())

        def _run():
            factory = DeviceFactory()
            return factory.run_scan(config)

        return await _run_in_thread(_run)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Device scan timed out")
    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error scanning devices")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/light/status", response_model=LightStatusResponse)
async def get_light_status():
    """Get light source status.

    A ``pwm_modbus`` light is queried with a side-effect-free register
    read-back (``PwmModbusLight.read_hardware_state``) -- no channel is ever
    written, so this can never turn a running laser off. It requires the
    hardware to be idle: refuses with 409 if the task queue is mid-job rather
    than opening a second connection on the same serial port a running
    workflow may already hold.
    """
    try:
        config = load_devices_config(default_devices_config_path())
    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    if config.light.type != "pwm_modbus":
        # Manual (or any non-hardware-backed) light: nothing to read: report
        # the software-only configuration state.
        return LightStatusResponse(
            type=config.light.type,
            manual_control=config.light.manual_light_control,
            available=True,
        )

    if task_queue.is_hardware_busy():
        raise HTTPException(status_code=409, detail="任务正在使用硬件，无法查询")

    def _read():
        factory = DeviceFactory()
        # initial_all_off=False: this is a read-only status query, it must
        # not force any channel off (that would be an unannounced light-off
        # side effect on a GET request).
        light = factory.create_light(config, initial_all_off=False)
        try:
            return light.read_hardware_state()
        finally:
            light.close(all_off=False)

    try:
        hardware_state = await _run_in_thread(_read)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timed out reading light hardware state")
    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error getting light status")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    return LightStatusResponse(
        type=config.light.type,
        manual_control=config.light.manual_light_control,
        available=True,
        hardware_state=hardware_state,
    )


# NOTE: POST /light/on was intentionally removed -- not renamed, not merged
# into another endpoint. An unauthenticated "turn the laser on" HTTP endpoint
# is a CSRF attack surface (any page the operator's browser has open could
# silently POST to it), and the frontend never called it. Turning the laser
# on is only ever done through a workflow run (SinglePointRequest with
# mode="real"/confirm_real=True, gated by ManualLight/PwmModbusLight's own
# on-confirmation). This router does not grow a replacement "turn on"
# capability.


@router.post("/light/off")
async def turn_light_off():
    """Force the light source off (all channels, read-back confirmed).

    Unlike the other endpoints in this router, a busy hardware executor does
    NOT refuse this request: off is the safe direction, and "the hardware is
    busy" is exactly the situation an operator reaching for an off switch is
    in. If the task queue is mid-job, every job is cancelled first
    (``task_queue.cancel_all()``) and this still attempts to force the light
    off afterwards; the response says plainly whether a cancellation happened
    first.
    """
    cancelled_jobs: list[str] = []
    if task_queue.is_hardware_busy():
        cancelled_jobs = await task_queue.cancel_all()
        try:
            if await _run_in_thread(task_queue.force_active_light_off):
                return {
                    "status": "off",
                    "message": f"Cancelled {len(cancelled_jobs)} running job(s), then turned light off successfully",
                    "cancelled_jobs": cancelled_jobs,
                    "hardware_state": None,
                }
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="Timed out turning off active light")
        except (ConfigError, DeviceError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    try:
        config_path = task_queue.safety_devices_path() or default_devices_config_path()
        config = load_devices_config(config_path)
    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    if config.light.type != "pwm_modbus":
        return {
            "status": "manual",
            "message": "Light is configured for manual control. Please turn off manually.",
        }

    def _turn_off():
        factory = DeviceFactory()
        light = factory.create_light(config, initial_all_off=False)
        try:
            light.safety_reset()
            return light.read_hardware_state()
        finally:
            light.close(all_off=False)

    try:
        hardware_state = await _run_in_thread(_turn_off)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timed out turning off light")
    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error turning light off")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

    message = "Light turned off successfully"
    if cancelled_jobs:
        message = (
            f"Cancelled {len(cancelled_jobs)} running job(s), then turned light off successfully"
        )
    return {
        "status": "off",
        "message": message,
        "cancelled_jobs": cancelled_jobs,
        "hardware_state": hardware_state,
    }
