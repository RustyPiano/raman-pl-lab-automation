import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from lab_auto.config import StageConfig
from lab_auto.devices.raw.waynelabs_protocol import Completed, LimitOrHome, ProtocolError, WaynelabsRawProtocol
from lab_auto.errors import ConfigError, DeviceError, SafetyError
from lab_auto.storage import write_json


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
        write_json(config.state_file, {
            "states": {axis: state.value for axis, state in self.states.items()},
            "position_um": self.position_um,
            "in_flight": self.in_flight,
            "resolution_um": config.resolution_um,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "device_identity": {"type": config.type, "port": config.port},
        })


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
        quotient = abs(um) / self.config.resolution_um[axis]
        if not math.isfinite(quotient):
            raise ConfigError("stage move distance produces invalid hardware steps")
        return round(quotient)

    def _commanded_um(self, *, axis: str, requested_um: float, steps: int) -> float:
        sign = 1.0 if requested_um >= 0 else -1.0
        return sign * steps * self.config.resolution_um[axis]

    def _assert_safe_move(self, axis: str, um: float) -> None:
        state = self.ledger.states.get(axis, AxisState.UNKNOWN)
        if state is AxisState.UNKNOWN and abs(um) > self.config.max_unknown_move_um:
            raise SafetyError("unknown position only allows small relative moves")
        if state is not AxisState.UNKNOWN:
            new_position = self.ledger.position_um[axis] + um
            low, high = self.config.soft_limits_um[axis]
            # 写成区间包含判断，台账位置为 NaN 时也会拒绝
            if not low <= new_position <= high:
                raise SafetyError(f"move exceeds soft limit for axis {axis}")

    def _assert_axis_supported(self, axis: str) -> None:
        # config 已保证 resolution_um 与 soft_limits_um 的轴集合相同
        if axis not in self.config.resolution_um:
            raise ConfigError(f"unsupported stage axis: {axis}")

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

    def _write(self, command: str) -> None:
        # 写命令前丢弃迟到的字节，避免上一条响应或噪声被误读成本条命令的完成标记
        self.transport.reset_input_buffer()
        try:
            self.transport.write(command.encode("ascii"))
        except Exception as exc:
            raise DeviceError(f"WayneLabs serial write failed: {exc}") from exc

    def _readline(self) -> str:
        # 串口异常统一转成 DeviceError，移动流程据此把该轴标记为 UNKNOWN
        try:
            return self.transport.readline().decode("ascii", errors="replace")
        except Exception as exc:
            raise DeviceError(f"WayneLabs serial read failed: {exc}") from exc

    def _send_command(self, command: str, *, timeout_s: float) -> Completed | LimitOrHome | None:
        if self.dry_run:
            return None
        self._write(command)
        deadline = time.monotonic() + timeout_s
        last_response = ""
        buffer = ""
        while time.monotonic() < deadline:
            response = self._readline()
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
            response = self._readline()
            if response:
                return response
            time.sleep(0.01)
        raise DeviceError("WayneLabs identify timed out waiting for device info")

    def _assert_no_trailing_response(self) -> None:
        response = self._readline()
        if response.strip():
            raise DeviceError(f"unexpected WayneLabs trailing response after completion: {response!r}")

    def _drain_identify_followup_responses(self) -> list[str]:
        responses = []
        idle_deadline = time.monotonic() + WAYNELABS_IDENTIFY_DRAIN_IDLE_TIMEOUT_S
        while len(responses) < 3 and time.monotonic() < idle_deadline:
            response = self._readline()
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
        self._assert_axis_supported(axis)
        if not math.isfinite(um):
            raise ConfigError("stage move distance must be finite")
        steps = self._steps_for_um(axis, um)
        if um != 0 and steps == 0:
            raise ConfigError("stage move distance rounds to zero hardware steps")
        commanded_um = self._commanded_um(axis=axis, requested_um=um, steps=steps)
        self._assert_safe_move(axis, commanded_um)
        direction = "positive" if um >= 0 else "negative"
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
        if self.dry_run:
            return {"type": self.config.type, "port": self.config.port}
        self._write(self.protocol.build_identify_command())
        responses = [self._read_identify_first_response()]
        responses.extend(self._drain_identify_followup_responses())
        try:
            info = self.protocol.parse_device_info(responses[0])
        except ProtocolError as exc:
            raise DeviceError(f"unexpected WayneLabs identify response: {responses[0]!r}") from exc
        if info.device_code != "X":
            raise DeviceError(f"WayneLabs device code {info.device_code!r} is not a linear stage controller")
        return {"type": info.device_type, "port": self.config.port, "device_code": info.device_code, "raw": "".join(responses)}

    def home(self, *, axis: str, direction: str, speed: int) -> list[str]:
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
