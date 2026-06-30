"""Device management API endpoints."""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from lab_auto.api.models import DeviceStatusResponse, LightStatusResponse
from lab_auto.config import load_devices_config
from lab_auto.devices.factory import DeviceFactory
from lab_auto.errors import ConfigError, DeviceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("/status", response_model=DeviceStatusResponse)
async def get_device_status(devices_config: str = "configs/devices.yaml"):
    """Get status of all devices."""
    try:
        config = load_devices_config(Path(devices_config))
        factory = DeviceFactory()
        status = factory.run_status(config)
        return DeviceStatusResponse(**status)
    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error getting device status")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/scan")
async def scan_devices(devices_config: str = "configs/devices.yaml"):
    """Scan for available devices."""
    try:
        config = load_devices_config(Path(devices_config))
        factory = DeviceFactory()
        scan_result = factory.run_scan(config)
        return scan_result
    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error scanning devices")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/light/status", response_model=LightStatusResponse)
async def get_light_status(devices_config: str = "configs/devices.yaml"):
    """Get light source status."""
    try:
        config = load_devices_config(Path(devices_config))
        factory = DeviceFactory()
        light = factory.create_light(config)

        try:
            # Try to determine if light is on (only for PWM/Modbus types)
            is_on = None
            if hasattr(light, 'is_on'):
                try:
                    is_on = light.is_on()
                except Exception:
                    pass

            return LightStatusResponse(
                type=config.light.type,
                is_on=is_on,
                manual_control=config.light.manual_light_control,
                available=True,
            )
        finally:
            if hasattr(light, 'close'):
                light.close()

    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error getting light status")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/light/on")
async def turn_light_on(devices_config: str = "configs/devices.yaml"):
    """Turn on light source (with safety checks)."""
    try:
        config = load_devices_config(Path(devices_config))

        if config.light.manual_light_control:
            return {
                "status": "manual",
                "message": "Light is configured for manual control. Please turn on manually.",
            }

        factory = DeviceFactory()
        light = factory.create_light(config)

        try:
            if hasattr(light, 'turn_on'):
                light.turn_on()
                return {"status": "on", "message": "Light turned on successfully"}
            else:
                return {
                    "status": "unsupported",
                    "message": f"Light type {config.light.type} does not support programmatic control",
                }
        finally:
            if hasattr(light, 'close'):
                light.close()

    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error turning light on")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.post("/light/off")
async def turn_light_off(devices_config: str = "configs/devices.yaml"):
    """Turn off light source."""
    try:
        config = load_devices_config(Path(devices_config))

        if config.light.manual_light_control:
            return {
                "status": "manual",
                "message": "Light is configured for manual control. Please turn off manually.",
            }

        factory = DeviceFactory()
        light = factory.create_light(config)

        try:
            if hasattr(light, 'turn_off'):
                light.turn_off()
                return {"status": "off", "message": "Light turned off successfully"}
            else:
                return {
                    "status": "unsupported",
                    "message": f"Light type {config.light.type} does not support programmatic control",
                }
        finally:
            if hasattr(light, 'close'):
                light.close()

    except (ConfigError, DeviceError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Error turning light off")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
