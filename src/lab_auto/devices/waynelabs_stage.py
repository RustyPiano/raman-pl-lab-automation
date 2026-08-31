import json
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from lab_auto.config import StageConfig
from lab_auto.devices.raw.waynelabs_protocol import Completed, LimitOrHome, ProtocolError, WaynelabsRawProtocol
from lab_auto.errors import ConfigError, DeviceError, SafetyError


WAYNELABS_SERIAL_READ_TIMEOUT_S = 0.25
WAYNELABS_IDENTIFY_TIMEOUT_S = 5.0
WAYNELABS_IDENTIFY_DRAIN_IDLE_TIMEOUT_S = 1.0
WAYNELABS_MOVE_TIMEOUT_S = 120.0
WAYNELABS_HOME_TIMEOUT_S = 300.0
WAYNELABS_TRIGGER_TIMEOUT_S = 30.0


class AxisState(str, Enum):
    UNKNOWN = "unknown"
    HOMED = "homed"
    USER_ZEROED = "user_zeroed"


@dataclass
class PositionLedger:
    states: dict[str, AxisState] = field(default_factory=lambda: {"x": AxisState.UNKNOWN, "y": AxisState.UNKNOWN, "z": AxisState.UNKNOWN})
    position_um: dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    # Axes with a move/home command in flight. Persisted BEFORE the motor starts
    # and cleared only after it completes, so a crash mid-move leaves a marker that
    # forces the axis back to UNKNOWN on the next load (position no longer trusted).
    in_flight: dict[str, dict] = field(default_factory=dict)

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
            states = {axis: AxisState(value) for axis, value in data["states"].items()}
            position_um = {axis: float(value) for axis, value in data["position_um"].items()}
            if any(not math.isfinite(value) for value in position_um.values()):
                return cls()
            # Back-compat: older ledgers have no in_flight field.
            in_flight = data.get("in_flight") or {}
            if not isinstance(in_flight, dict):
                in_flight = {}
            # An axis whose move/home never completed cannot be trusted: the motor
            # may have moved after the last persisted position. Force it UNKNOWN.
            for axis in in_flight:
                if axis in states:
                    states[axis] = AxisState.UNKNOWN
            for axis, state in states.items():
                if state is not AxisState.UNKNOWN and axis not in position_um:
                    return cls()
            return cls(
                states=states,
                position_um=position_um,
                in_flight=dict(in_flight),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return cls()

    def save(self, config: StageConfig) -> None:
        config.state_file.parent.mkdir(parents=True, exist_ok=True)
        # Atomic: write a sibling temp file then os.replace it in, so a crash/power
        # loss mid-write leaves the previous complete ledger intact (write_text
        # truncates first, so a partial write would otherwise be unloadable).
        tmp = config.state_file.with_name(config.state_file.name + ".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "states": {axis: state.value for axis, state in self.states.items()},
                    "position_um": self.position_um,
                    "in_flight": self.in_flight,
                    "resolution_um": config.resolution_um,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "device_identity": {"type": config.type, "port": config.port},
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        os.replace(tmp, config.state_file)


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
        try:
            quotient = abs(um) / self.config.resolution_um[axis]
            if not math.isfinite(quotient):
                raise ConfigError("stage move distance produces invalid hardware steps")
            return round(quotient)
        except OverflowError as exc:
            raise ConfigError("stage move distance produces invalid hardware steps") from exc

    def _direction_for_um(self, um: float) -> str:
        return "positive" if um >= 0 else "negative"

    def _is_finite_move_distance(self, um: float) -> bool:
        if not isinstance(um, (int, float)) or isinstance(um, bool):
            return False
        try:
            number = float(um)
        except (OverflowError, TypeError, ValueError):
            return False
        return math.isfinite(number)

    def _commanded_um(self, *, axis: str, requested_um: float, steps: int) -> float:
        sign = 1.0 if requested_um >= 0 else -1.0
        return sign * steps * self.config.resolution_um[axis]

    def _assert_safe_move(self, axis: str, um: float) -> None:
        self._assert_axis_supported(axis)
        if not self._is_finite_move_distance(um):
            raise ConfigError("stage move distance must be finite")
        state = self.ledger.states.get(axis, AxisState.UNKNOWN)
        if state is AxisState.UNKNOWN and abs(um) > self.config.max_unknown_move_um:
            raise SafetyError("unknown position only allows small relative moves")
        if state is not AxisState.UNKNOWN:
            if axis not in self.ledger.position_um or not math.isfinite(self.ledger.position_um[axis]):
                raise SafetyError(f"known position for axis {axis} is missing or invalid")
            new_position = self.ledger.position_um[axis] + um
            low, high = self.config.soft_limits_um[axis]
            if new_position < low or new_position > high:
                raise SafetyError(f"move exceeds soft limit for axis {axis}")

    def _assert_axis_supported(self, axis: str) -> None:
        if axis not in self.config.resolution_um or axis not in self.config.soft_limits_um:
            raise ConfigError(f"unsupported stage axis: {axis}")

    def _assert_linear_controller(self) -> None:
        if self.config.type != "waynelabs_linear":
            raise DeviceError("WayneLabs movement requires a waynelabs_linear stage")

    def _parse_completion_buffer(self, buffer: str) -> Completed | LimitOrHome | None:
        text = "".join(buffer.split())
        index = 0
        while index < len(text):
            if text[index] != "?":
                raise ProtocolError(f"unexpected completion response: {buffer!r}")
            if index + 1 >= len(text):
                return None
            if text[index + 1] == "?":
                index += 1
                continue
            if index + 2 != len(text):
                raise ProtocolError(f"unexpected completion response: {buffer!r}")
            return self.protocol.parse_completion(text[index : index + 2])
        return None

    def _reset_input_buffer(self) -> None:
        # Drop stale/late bytes before writing a command, so a prior response or a
        # noise byte can't be misread as this command's completion. getattr-guarded
        # so transports without the method (or None) are a no-op.
        reset = getattr(self.transport, "reset_input_buffer", None)
        if reset is not None:
            reset()

    def _send_command(self, command: str, *, timeout_s: float) -> Completed | LimitOrHome | None:
        if self.dry_run or self.transport is None:
            return None
        self._reset_input_buffer()
        try:
            self.transport.write(command.encode("ascii"))
        except Exception as exc:
            raise DeviceError(f"WayneLabs serial write failed: {exc}") from exc
        deadline = time.monotonic() + timeout_s
        last_response = ""
        buffer = ""
        while time.monotonic() < deadline:
            try:
                response = self.transport.readline().decode("ascii", errors="replace")
            except Exception as exc:
                raise DeviceError(f"WayneLabs serial read failed: {exc}") from exc
            last_response = response
            buffer += response
            try:
                result = self._parse_completion_buffer(buffer)
            except ProtocolError as exc:
                raise DeviceError(f"unexpected WayneLabs completion response: {buffer!r}") from exc
            if result is None:
                time.sleep(0.01)
                continue
            self._assert_no_trailing_response()
            return result
        raise DeviceError(f"WayneLabs command timed out waiting for completion response: {last_response!r}")

    def _read_identify_first_response(self) -> str:
        deadline = time.monotonic() + WAYNELABS_IDENTIFY_TIMEOUT_S
        while time.monotonic() < deadline:
            try:
                response = self.transport.readline().decode("ascii", errors="replace")
            except Exception as exc:
                raise DeviceError(f"WayneLabs serial read failed: {exc}") from exc
            if response:
                return response
            time.sleep(0.01)
        raise DeviceError("WayneLabs identify timed out waiting for device info")

    def _assert_no_trailing_response(self) -> None:
        try:
            response = self.transport.readline().decode("ascii", errors="replace")
        except Exception as exc:
            raise DeviceError(f"WayneLabs serial read failed: {exc}") from exc
        if response.strip():
            raise DeviceError(f"unexpected WayneLabs trailing response after completion: {response!r}")

    def _drain_identify_followup_responses(self) -> list[str]:
        responses = []
        idle_deadline = time.monotonic() + WAYNELABS_IDENTIFY_DRAIN_IDLE_TIMEOUT_S
        while len(responses) < 3 and time.monotonic() < idle_deadline:
            try:
                response = self.transport.readline().decode("ascii", errors="replace")
            except Exception as exc:
                raise DeviceError(f"WayneLabs serial read failed: {exc}") from exc
            if response:
                responses.append(response)
                idle_deadline = time.monotonic() + WAYNELABS_IDENTIFY_DRAIN_IDLE_TIMEOUT_S
                continue
            time.sleep(0.01)
        return responses

    def _save_ledger(self) -> None:
        self.ledger.save(self.config)

    def _mark_axis_unknown(self, axis: str) -> None:
        self.ledger.states[axis] = AxisState.UNKNOWN
        self.ledger.in_flight.pop(axis, None)
        self._save_ledger()

    def move_relative(self, *, axis: str, um: float, speed: int) -> list[str]:
        self._assert_linear_controller()
        self._assert_axis_supported(axis)
        if not self._is_finite_move_distance(um):
            raise ConfigError("stage move distance must be finite")
        steps = self._steps_for_um(axis, um)
        if um != 0 and steps == 0:
            raise ConfigError("stage move distance rounds to zero hardware steps")
        commanded_um = self._commanded_um(axis=axis, requested_um=um, steps=steps)
        self._assert_safe_move(axis, commanded_um)
        direction = self._direction_for_um(um)
        try:
            commands = [
                self.protocol.build_move_command(axis=axis, steps=chunk, speed=speed, direction=direction)
                for chunk in self.protocol.split_steps(steps)
            ]
        except ProtocolError as exc:
            raise ConfigError(str(exc)) from exc
        if not self.dry_run:
            # Two-phase: persist the in-flight marker BEFORE the motor starts. If we
            # are killed mid-move, load() forces this axis UNKNOWN (position stale).
            self.ledger.in_flight[axis] = {"commanded_um": commanded_um}
            self._save_ledger()
        for command in commands:
            try:
                result = self._send_command(command, timeout_s=WAYNELABS_MOVE_TIMEOUT_S)
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
        # Move complete: commit the new position (known axes) and clear in-flight.
        if self.ledger.states.get(axis, AxisState.UNKNOWN) is not AxisState.UNKNOWN:
            self.ledger.position_um[axis] = self.ledger.position_um[axis] + commanded_um
        self.ledger.in_flight.pop(axis, None)
        self._save_ledger()
        return commands

    def identify(self) -> dict:
        if self.dry_run or self.transport is None:
            return {"type": self.config.type, "port": self.config.port}
        command = self.protocol.build_identify_command()
        self._reset_input_buffer()
        try:
            self.transport.write(command.encode("ascii"))
        except Exception as exc:
            raise DeviceError(f"WayneLabs serial write failed: {exc}") from exc
        responses = [self._read_identify_first_response()]
        responses.extend(self._drain_identify_followup_responses())
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
        # A limit hit in EITHER direction returns the same "?t" marker, so homing the
        # wrong way records the far limit as origin 0.0 and inverts the whole axis
        # (soft limits then guard the wrong side). Refuse any direction that doesn't
        # match the configured, on-rig-verified safe home direction.
        if self.config.home_direction is None:
            if not self.dry_run:
                raise SafetyError(
                    f"axis {axis} has no configured safe home direction; verify it on the rig before homing"
                )
        elif direction != self.config.home_direction[axis]:
            raise SafetyError(
                f"home direction {direction!r} does not match the configured safe home "
                f"direction {self.config.home_direction[axis]!r} for axis {axis}"
            )
        try:
            command = self.protocol.build_home_command(axis=axis, speed=speed, direction=direction)
        except ProtocolError as exc:
            raise ConfigError(str(exc)) from exc
        if not self.dry_run:
            # Two-phase: mark in-flight before the motor starts (see move_relative).
            self.ledger.in_flight[axis] = {"home": True, "direction": direction}
            self._save_ledger()
        try:
            result = self._send_command(command, timeout_s=WAYNELABS_HOME_TIMEOUT_S)
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
        self.ledger.in_flight.pop(axis, None)
        self._save_ledger()
        return [command]

    def trigger(self, *, mode: str) -> list[str]:
        self._assert_linear_controller()
        try:
            command = self.protocol.build_trigger_command(mode=mode)
        except ProtocolError as exc:
            raise ConfigError(str(exc)) from exc
        result = self._send_command(command, timeout_s=WAYNELABS_TRIGGER_TIMEOUT_S)
        if isinstance(result, LimitOrHome):
            raise DeviceError("WayneLabs trigger returned limit marker")
        if isinstance(result, Completed) and result.direction != command[-1]:
            raise DeviceError("WayneLabs trigger returned unexpected completion marker")
        return [command]

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()
