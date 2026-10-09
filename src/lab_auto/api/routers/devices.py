"""Device management API endpoints."""
import asyncio
from fastapi import APIRouter

from lab_auto.api.models import DeviceStatusResponse, LightStatusResponse
from lab_auto.api.paths import default_devices_config_path
from lab_auto.api.task_queue import task_queue
from lab_auto.config import load_devices_config
from lab_auto.devices.factory import DeviceFactory

router = APIRouter(prefix="/api/devices", tags=["devices"])

# Diagnostics share the workflow executor. Emergency OFF alone uses the active
# light handle outside that executor, so it can interrupt a blocked acquisition.
_HARDWARE_CALL_TIMEOUT_S = 15


async def _run_in_thread(fn, *, require_idle: bool = True):
    """Run a blocking hardware call off the event loop, with a bounded wait.

    A busy executor raises HardwareBusyError (409) and a timeout raises
    TimeoutError (504); both are mapped by the app-level exception handlers.
    """
    return await asyncio.wait_for(
        task_queue.run_device_operation(fn, require_idle=require_idle),
        timeout=_HARDWARE_CALL_TIMEOUT_S,
    )


@router.get("/status", response_model=DeviceStatusResponse)
async def get_device_status():
    """Get status of all devices."""
    config = load_devices_config(default_devices_config_path())
    return DeviceStatusResponse(**await _run_in_thread(lambda: DeviceFactory().run_status(config)))


@router.post("/scan")
async def scan_devices():
    """Scan for available devices."""
    config = load_devices_config(default_devices_config_path())
    return await _run_in_thread(lambda: DeviceFactory().run_scan(config))


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
    config = load_devices_config(default_devices_config_path())
    if config.light.type != "pwm_modbus":
        # Manual light: nothing to read, report the configuration only.
        return LightStatusResponse(
            type=config.light.type,
            manual_control=config.light.manual_light_control,
            available=True,
        )

    def _read():
        # initial_all_off=False: this is a read-only status query, it must
        # not force any channel off (that would be an unannounced light-off
        # side effect on a GET request).
        light = DeviceFactory().create_light(config, initial_all_off=False)
        try:
            return light.read_hardware_state()
        finally:
            light.close(all_off=False)

    return LightStatusResponse(
        type=config.light.type,
        manual_control=config.light.manual_light_control,
        available=True,
        hardware_state=await _run_in_thread(_read),
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
        off = asyncio.get_running_loop().run_in_executor(None, task_queue.force_active_light_off)
        if await asyncio.wait_for(off, timeout=_HARDWARE_CALL_TIMEOUT_S):
            return {
                "status": "off",
                "message": f"已取消 {len(cancelled_jobs)} 个任务，光源已全部关闭",
                "cancelled_jobs": cancelled_jobs,
                "hardware_state": None,
            }

    config = load_devices_config(task_queue.safety_devices_path() or default_devices_config_path())
    if config.light.type != "pwm_modbus":
        return {
            "status": "manual",
            "message": "光源为人工控制，请在实验台手动关闭",
        }

    def _turn_off():
        light = DeviceFactory().create_light(config, initial_all_off=False)
        try:
            light.safety_reset()
            return light.read_hardware_state()
        finally:
            light.close(all_off=False)

    hardware_state = await _run_in_thread(_turn_off, require_idle=False)
    message = "光源已全部关闭"
    if cancelled_jobs:
        message = f"已取消 {len(cancelled_jobs)} 个任务，光源已全部关闭"
    return {
        "status": "off",
        "message": message,
        "cancelled_jobs": cancelled_jobs,
        "hardware_state": hardware_state,
    }
