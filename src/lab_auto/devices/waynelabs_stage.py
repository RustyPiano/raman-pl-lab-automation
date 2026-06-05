import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from lab_auto.config import StageConfig
from lab_auto.devices.raw.waynelabs_protocol import Completed, LimitOrHome, ProtocolError, WaynelabsRawProtocol
from lab_auto.errors import ConfigError, DeviceError, SafetyError


class AxisState(str, Enum):
    UNKNOWN = "unknown"
    HOMED = "homed"
    USER_ZEROED = "user_zeroed"


@dataclass
class PositionLedger:
    states: dict[str, AxisState] = field(default_factory=lambda: {"x": AxisState.UNKNOWN, "y": AxisState.UNKNOWN, "z": AxisState.UNKNOWN})
    position_um: dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})

    @classmethod
    def load(cls, config: StageConfig) -> "PositionLedger":
        path = config.state_file
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("resolution_um") != config.resolution_um:
                return cls()
            identity = data.get("device_identity", {})
            if identity.get("type") != config.type or identity.get("port") != config.port:
                return cls()
            return cls(
                states={axis: AxisState(value) for axis, value in data["states"].items()},
                position_um={axis: float(value) for axis, value in data["position_um"].items()},
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return cls()

    def save(self, config: StageConfig) -> None:
        config.state_file.parent.mkdir(parents=True, exist_ok=True)
        config.state_file.write_text(
            json.dumps(
                {
                    "states": {axis: state.value for axis, state in self.states.items()},
                    "position_um": self.position_um,
                    "resolution_um": config.resolution_um,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "device_identity": {"type": config.type, "port": config.port},
                },
                indent=2,
            ),
            encoding="utf-8",
        )


class WaynelabsStage:
    def __init__(
        self,
        config: StageConfig,
        *,
        transport,
        dry_run: bool,
        ledger: PositionLedger | None = None,
        protocol: WaynelabsRawProtocol | None = None,
    ):
        self.config = config
        self.transport = transport
        self.dry_run = dry_run
        self.ledger = ledger or PositionLedger()
        self.protocol = protocol or WaynelabsRawProtocol()

    def _steps_for_um(self, axis: str, um: float) -> int:
        self._assert_axis_supported(axis)
        return round(abs(um) / self.config.resolution_um[axis])

    def _direction_for_um(self, um: float) -> str:
        return "positive" if um >= 0 else "negative"

    def _assert_safe_move(self, axis: str, um: float) -> None:
        self._assert_axis_supported(axis)
        state = self.ledger.states.get(axis, AxisState.UNKNOWN)
        if state is AxisState.UNKNOWN and abs(um) > self.config.max_unknown_move_um:
            raise SafetyError("unknown position only allows small relative moves")
        if state is not AxisState.UNKNOWN:
            new_position = self.ledger.position_um.get(axis, 0.0) + um
            low, high = self.config.soft_limits_um[axis]
            if new_position < low or new_position > high:
                raise SafetyError(f"move exceeds soft limit for axis {axis}")

    def _assert_axis_supported(self, axis: str) -> None:
        if axis not in self.config.resolution_um or axis not in self.config.soft_limits_um:
            raise ConfigError(f"unsupported stage axis: {axis}")

    def _assert_linear_controller(self) -> None:
        if self.config.type != "waynelabs_linear":
            raise DeviceError("WayneLabs movement requires a waynelabs_linear stage")

    def _send_command(self, command: str) -> Completed | LimitOrHome | None:
        if self.dry_run or self.transport is None:
            return None
        self.transport.write(command.encode("ascii"))
        response = self.transport.readline().decode("ascii", errors="replace")
        try:
            return self.protocol.parse_completion(response)
        except ProtocolError as exc:
            raise DeviceError(f"unexpected WayneLabs completion response: {response!r}") from exc

    def _save_ledger(self) -> None:
        self.ledger.save(self.config)

    def _mark_axis_unknown(self, axis: str) -> None:
        self.ledger.states[axis] = AxisState.UNKNOWN
        self._save_ledger()

    def move_relative(self, *, axis: str, um: float, speed: int) -> list[str]:
        self._assert_linear_controller()
        self._assert_safe_move(axis, um)
        direction = self._direction_for_um(um)
        try:
            commands = [
                self.protocol.build_move_command(axis=axis, steps=chunk, speed=speed, direction=direction)
                for chunk in self.protocol.split_steps(self._steps_for_um(axis, um))
            ]
        except ProtocolError as exc:
            raise ConfigError(str(exc)) from exc
        for command in commands:
            try:
                result = self._send_command(command)
            except DeviceError:
                self._mark_axis_unknown(axis)
                raise
            if result is None:
                continue
            if isinstance(result, LimitOrHome):
                self._mark_axis_unknown(axis)
                raise DeviceError(f"WayneLabs move hit limit for axis {axis}")
            if isinstance(result, Completed) and result.direction != command[-1]:
                self._mark_axis_unknown(axis)
                raise DeviceError(f"WayneLabs move completed in unexpected direction for axis {axis}")
        if self.dry_run:
            return commands
        if self.ledger.states.get(axis, AxisState.UNKNOWN) is not AxisState.UNKNOWN:
            self.ledger.position_um[axis] = self.ledger.position_um.get(axis, 0.0) + um
            self._save_ledger()
        return commands

    def identify(self) -> dict:
        if self.dry_run or self.transport is None:
            return {"type": self.config.type, "port": self.config.port}
        command = self.protocol.build_identify_command()
        self.transport.write(command.encode("ascii"))
        responses = [self.transport.readline().decode("ascii", errors="replace")]
        for _ in range(3):
            response = self.transport.readline().decode("ascii", errors="replace")
            if not response:
                break
            responses.append(response)
        try:
            info = self.protocol.parse_device_info(responses[0])
        except ProtocolError as exc:
            raise DeviceError(f"unexpected WayneLabs identify response: {responses[0]!r}") from exc
        if self.config.type == "waynelabs_linear" and info.device_code != "X":
            raise DeviceError(f"WayneLabs device code {info.device_code!r} is not a linear stage controller")
        return {"type": info.device_type, "port": self.config.port, "device_code": info.device_code, "raw": "".join(responses)}

    def home(self, *, axis: str, direction: str, speed: int) -> list[str]:
        self._assert_linear_controller()
        self._assert_axis_supported(axis)
        try:
            command = self.protocol.build_home_command(axis=axis, speed=speed, direction=direction)
        except ProtocolError as exc:
            raise ConfigError(str(exc)) from exc
        try:
            result = self._send_command(command)
        except DeviceError:
            self._mark_axis_unknown(axis)
            raise
        if result is None:
            return [command]
        if isinstance(result, Completed):
            self._mark_axis_unknown(axis)
            raise DeviceError(f"WayneLabs home did not report home completion for axis {axis}")
        self.ledger.states[axis] = AxisState.HOMED
        self.ledger.position_um[axis] = 0.0
        self._save_ledger()
        return [command]

    def trigger(self, *, mode: str) -> list[str]:
        self._assert_linear_controller()
        try:
            command = self.protocol.build_trigger_command(mode=mode)
        except ProtocolError as exc:
            raise ConfigError(str(exc)) from exc
        result = self._send_command(command)
        if isinstance(result, LimitOrHome):
            raise DeviceError("WayneLabs trigger returned limit marker")
        if isinstance(result, Completed) and result.direction != command[-1]:
            raise DeviceError("WayneLabs trigger returned unexpected completion marker")
        return [command]

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()
