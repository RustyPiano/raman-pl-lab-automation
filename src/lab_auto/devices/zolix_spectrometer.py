from lab_auto.errors import ConfigError, DeviceError
from lab_auto.devices.optics_validation import validate_zolix_optics


def require_ok(action: str, ok: bool) -> bool:
    if not ok:
        raise DeviceError(f"Zolix operation failed: {action}")
    return True


def direct_to_front_bool(port: str) -> bool:
    normalized = port.lower()
    if normalized in {"direct", "front"}:
        return True
    if normalized == "side":
        return False
    raise ConfigError(f"unsupported Zolix port: {port}")


def front_bool_to_port(value: bool) -> str:
    return "direct" if value else "side"


class ZolixSpectrometer:
    def __init__(self, raw, device_id: int):
        self.raw = raw
        self.device_id = device_id

    def status(self) -> dict:
        status = dict(self.raw.get_status(self.device_id))
        if hasattr(self.raw, "get_entrance_port"):
            status["entrance_port"] = front_bool_to_port(self.raw.get_entrance_port(self.device_id))
        if hasattr(self.raw, "get_exit_port"):
            status["exit_port"] = front_bool_to_port(self.raw.get_exit_port(self.device_id))
        if hasattr(self.raw, "get_grating"):
            status["grating"] = self.raw.get_grating(self.device_id)
        if hasattr(self.raw, "get_current_wavelength_nm"):
            status["current_wavelength_nm"] = self.raw.get_current_wavelength_nm(self.device_id)
        if hasattr(self.raw, "get_slit_width_um"):
            status["slit_width_um"] = self.raw.get_slit_width_um(self.device_id)
        return status

    def initialize(self, *, entrance_port: str, exit_port: str) -> bool:
        return self.set_entrance_port(entrance_port) and self.set_exit_port(exit_port)

    def set_entrance_port(self, port: str) -> bool:
        return require_ok("set_entrance_port", self.raw.set_entrance_port(self.device_id, direct_to_front_bool(port)))

    def set_exit_port(self, port: str) -> bool:
        return require_ok("set_exit_port", self.raw.set_exit_port(self.device_id, direct_to_front_bool(port)))

    def set_grating(self, grating: int) -> bool:
        validate_zolix_optics(grating=grating)
        return require_ok("set_grating", self.raw.set_grating(self.device_id, grating))

    def move_to_wavelength_nm(self, wavelength_nm: float) -> bool:
        validate_zolix_optics(wavelength_nm=wavelength_nm)
        return require_ok("move_to_wavelength_nm", self.raw.move_to_wavelength_nm(self.device_id, wavelength_nm))

    def set_slit_width_um(self, width_um: int) -> bool:
        validate_zolix_optics(slit_um=width_um)
        return require_ok("set_slit_width_um", self.raw.set_slit_width_um(self.device_id, width_um))

    def pixels_to_waves(
        self,
        *,
        turret: int,
        grating: int,
        center_wavelength_nm: float,
        width: int,
        count: int,
        bin_x: int,
    ) -> list[float]:
        return self.raw.pixels_to_waves(
            self.device_id,
            turret=turret,
            grating=grating,
            center_wavelength_nm=center_wavelength_nm,
            width=width,
            count=count,
            bin_x=bin_x,
        )

    def close(self) -> None:
        self.raw.close(self.device_id)
