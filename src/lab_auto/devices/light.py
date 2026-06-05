class ManualLight:
    def __init__(self, *, manual: bool):
        self.manual = manual
        self.laser_state = "unknown"
        self.led_state = "unknown"

    def require_off_confirmation(self) -> str:
        if self.manual:
            return "confirm_laser_off"
        return "laser_off"

    def require_on_confirmation(self) -> str:
        if self.manual:
            return "confirm_laser_on"
        return "laser_on"

    def confirm_laser_off(self, *, require_confirmation: bool) -> None:
        if self.manual and require_confirmation:
            input("Confirm laser is OFF, then press Enter: ")
        self.laser_state = "off_confirmed"

    def confirm_laser_on(self, *, require_confirmation: bool) -> None:
        if self.manual and require_confirmation:
            input("Confirm laser is ON, then press Enter: ")
        self.laser_state = "on_confirmed"

    def get_state(self) -> dict:
        return {"laser_state": self.laser_state, "led_state": self.led_state}
