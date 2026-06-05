from dataclasses import dataclass


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Completed:
    direction: str


@dataclass(frozen=True)
class LimitOrHome:
    marker: str = "t"


@dataclass(frozen=True)
class DeviceInfo:
    raw: str
    device_code: str
    device_type: str


DIRECTION_CODES = {
    ("x", "negative"): "b",
    ("x", "positive"): "c",
    ("y", "negative"): "d",
    ("y", "positive"): "e",
    ("z", "negative"): "f",
    ("z", "positive"): "g",
}

DEVICE_TYPES = {
    "A": "waynelabs_step_switch",
    "B": "waynelabs_filter_wheel",
    "C": "waynelabs_attenuator",
    "D": "waynelabs_rotation_mount",
    "R": "waynelabs_rotation_controller",
    "X": "waynelabs_linear",
    "Y": "waynelabs_linear_switching",
}


def split_steps(steps: int) -> list[int]:
    if steps < 0:
        raise ProtocolError("steps must be non-negative")
    chunks: list[int] = []
    remaining = steps
    while remaining > 9999:
        chunks.append(9999)
        remaining -= 9999
    if remaining:
        chunks.append(remaining)
    return chunks


def _direction_code(axis: str, direction: str) -> str:
    key = (axis.lower(), direction)
    if key not in DIRECTION_CODES:
        raise ProtocolError(f"unsupported axis/direction: {axis}/{direction}")
    return DIRECTION_CODES[key]


def _validate_speed(speed: int) -> None:
    if speed < 0 or speed > 9:
        raise ProtocolError("speed must be between 0 and 9")


def build_move_command(*, axis: str, steps: int, speed: int, direction: str) -> str:
    _validate_speed(speed)
    if steps < 1 or steps > 9999:
        raise ProtocolError("move steps must be between 1 and 9999")
    return f"?X{speed}{steps:04d}{_direction_code(axis, direction)}"


def build_home_command(*, axis: str, speed: int, direction: str) -> str:
    _validate_speed(speed)
    return f"?X{speed}0000{_direction_code(axis, direction)}"


def build_identify_command() -> str:
    return "?S000000"


def build_trigger_command(*, mode: str) -> str:
    if mode == "open_loop":
        return "?X11111q"
    if mode == "closed_loop":
        return "?X11111p"
    raise ProtocolError(f"unsupported trigger mode: {mode}")


def parse_device_info(response: str) -> DeviceInfo:
    if len(response) < 3 or not response.startswith("?"):
        raise ProtocolError(f"unexpected device info response: {response!r}")
    device_code = response[1]
    return DeviceInfo(
        raw=response,
        device_code=device_code,
        device_type=DEVICE_TYPES.get(device_code, "unknown"),
    )


def parse_completion(response: str) -> Completed | LimitOrHome:
    text = response.strip()
    if text == "?t":
        return LimitOrHome()
    if len(text) == 2 and text[0] == "?" and text[1] in "bcdefgpq":
        return Completed(direction=text[1])
    raise ProtocolError(f"unexpected completion response: {response!r}")


class WaynelabsRawProtocol:
    def split_steps(self, steps: int) -> list[int]:
        return split_steps(steps)

    def build_move_command(self, *, axis: str, steps: int, speed: int, direction: str) -> str:
        return build_move_command(axis=axis, steps=steps, speed=speed, direction=direction)

    def build_home_command(self, *, axis: str, speed: int, direction: str) -> str:
        return build_home_command(axis=axis, speed=speed, direction=direction)

    def build_identify_command(self) -> str:
        return build_identify_command()

    def build_trigger_command(self, *, mode: str) -> str:
        return build_trigger_command(mode=mode)

    def parse_device_info(self, response: str) -> DeviceInfo:
        return parse_device_info(response)

    def parse_completion(self, response: str) -> Completed | LimitOrHome:
        return parse_completion(response)
