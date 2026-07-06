import time

from lab_auto.config import LightConfig
from lab_auto.devices.raw.pwm_modbus import (
    EXCEPTION_RESPONSE_LEN,
    READ,
    VOLTAGE_REGISTER,
    WRITE_SINGLE,
    build_read_request,
    build_write_single_request,
    duty_register,
    expected_read_response_len,
    freq_registers,
    output_state_register,
    parse_read_response,
    parse_write_ack,
    ProtocolError,
    voltage_to_register,
)
from lab_auto.errors import DeviceError

PWM_MODBUS_READ_TIMEOUT_S = 1.0


class _ExchangeError(DeviceError):
    """Retryable Modbus exchange failure: a read timeout or an unparseable frame.

    A single late/stray byte left in the OS buffer after a prior timeout desyncs
    the RTU stream, so the next response is misread. These failures are retried
    once (flush + resend) by ``_retry_exchange``. A transport WRITE failure is a
    plain ``DeviceError`` instead, so it is never retried. Subclasses
    ``DeviceError`` so a retry that still fails surfaces uniformly.
    """


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


class PwmModbusLight:
    """Real PWM light backend over Modbus RTU with read-back-confirmed interlocks.

    Implements the same interface ``RamanWorkflow`` already drives on ``ManualLight``
    (``require_*_confirmation`` / ``confirm_laser_*`` / ``get_state``) plus the real
    ``laser_on``/``laser_off``/``led_on``/``led_off`` channel control. All framing is
    delegated to ``raw.pwm_modbus``; this layer only sequences reads and writes and
    tracks the laser/LED state machines from spec 12.2.
    """

    def __init__(self, config: LightConfig, *, transport, dry_run: bool):
        self.config = config
        self.transport = transport
        self.dry_run = dry_run
        self.station = config.station_id
        self.laser_state = "unknown"
        self.led_state = "unknown"

    # --- workflow-facing interface (matches ManualLight) ---------------

    def require_off_confirmation(self) -> str:
        return "laser_off"

    def require_on_confirmation(self) -> str:
        return "laser_on"

    def confirm_laser_off(self, *, require_confirmation: bool) -> None:
        self.laser_off()

    def confirm_laser_on(self, *, require_confirmation: bool) -> None:
        self.laser_on()

    def get_state(self) -> dict:
        return {"laser_state": self.laser_state, "led_state": self.led_state}

    def read_hardware_state(self) -> dict:
        """Side-effect-free register read-back for status endpoints.

        Reads Reg1 (voltage) and the 5 output-state registers straight from the
        controller (no channel writes), so a read-only status query reflects real
        hardware rather than only the software state machine. dry_run returns the
        software state.
        """
        if self.dry_run:
            return {"laser_state": self.laser_state, "led_state": self.led_state}
        voltage = self._read(VOLTAGE_REGISTER, 1)[0]
        states = self._read(output_state_register(1), 5)
        channel_states = dict(zip(self._ALL_CHANNELS, states))
        return {
            "voltage_register": voltage,
            "channel_states": channel_states,
            "laser_state": self.laser_state,
            "led_state": self.led_state,
        }

    def safety_reset(self) -> None:
        """Force every channel off with read-back confirmation (power-on / e-stop).

        Reused as the power-on safety reset in the factory and for any emergency
        stop path. Raises ``DeviceError`` if a CONFIGURED channel cannot be
        confirmed OFF.
        """
        if self.dry_run:
            self.laser_state = "off_confirmed"
            self.led_state = "off_confirmed"
            return
        failures = self._all_off_with_retry()
        if failures:
            self.laser_state = "manual_wait"
            raise DeviceError(f"power-on safety reset failed to confirm channels OFF: {sorted(failures)}")
        self.laser_state = "off_confirmed"
        self.led_state = "off_confirmed"

    def close(self, *, all_off: bool = True) -> None:
        # Safety net: force every channel off before dropping the transport, so a
        # failure path that left the laser on gets one last chance to turn it off.
        # ``all_off=False`` is for read-only status teardown that must not touch
        # any channel.
        if all_off and not self.dry_run:
            try:
                self._all_off()
            except Exception:  # noqa: BLE001 - teardown must never be blocked
                pass
        close = getattr(self.transport, "close", None)
        if close is not None:
            close()

    # --- channel control ----------------------------------------------

    def laser_on(self) -> None:
        if self.dry_run:
            self.laser_state = "on_confirmed"
            return
        self._open_channel(self._channel("laser"))
        self.laser_state = "on_confirmed"

    def led_on(self) -> None:
        if self.dry_run:
            self.led_state = "on_confirmed"
            return
        self._open_channel(self._channel("led"))
        self.led_state = "on_confirmed"  # never satisfies the laser precondition

    def laser_off(self) -> None:
        if self.dry_run:
            self.laser_state = "off_confirmed"
            return
        failures = self._all_off_with_retry()
        if failures:
            self.laser_state = "manual_wait"
            raise DeviceError(f"failed to confirm laser OFF for channels: {sorted(failures)}")
        self.laser_state = "off_confirmed"
        self.led_state = "off_confirmed"

    def led_off(self) -> None:
        if self.dry_run:
            self.led_state = "off_confirmed"
            return
        failures = self._all_off_with_retry()
        if failures:
            self.led_state = "manual_wait"
            raise DeviceError(f"failed to confirm LED OFF for channels: {sorted(failures)}")
        self.laser_state = "off_confirmed"
        self.led_state = "off_confirmed"

    def ensure_voltage_setpoint(self) -> None:
        """Guarded Reg1 write: only when every channel reads back off.

        One-time SETUP step: establishes the laser voltage setpoint that every
        ``laser_on``/``led_on`` later re-verifies via ``_verify_voltage``. It is
        intentionally NOT auto-called on the per-shot enable path (that path only
        verifies, never writes), so the operator/setup must call this once before
        laser use. TODO(hardware): confirm where Reg1 is established on the real
        controller — if it isn't persisted across power cycles, wire this into the
        bring-up sequence.
        """
        if self.dry_run:
            return
        states = self._read(output_state_register(1), 5)
        if any(state != 0 for state in states):
            raise DeviceError("cannot write Reg1 while any PWM channel is on")
        target = voltage_to_register(self.config.required_output_voltage_v)
        self._write_single(VOLTAGE_REGISTER, target)
        if self._read(VOLTAGE_REGISTER, 1)[0] != target:
            raise DeviceError("Reg1 voltage readback mismatch after write")

    # --- internals -----------------------------------------------------

    def _channel(self, name: str):
        channel = (self.config.channels or {}).get(name)
        if channel is None:
            raise DeviceError(f"no PWM channel mapping configured for '{name}'")
        return channel

    def _open_channel(self, channel) -> None:
        self._verify_voltage()
        self._verify_other_channels_off(channel.channel)
        self._verify_channel_setpoints(channel)
        register = output_state_register(channel.channel)
        self._write_single(register, 1)
        if self._read(register, 1)[0] != 1:
            raise DeviceError(f"output-state readback for channel {channel.channel} is not 1")

    def _verify_voltage(self) -> None:
        target = voltage_to_register(self.config.required_output_voltage_v)
        value = self._read(VOLTAGE_REGISTER, 1)[0]
        if value != target:
            raise DeviceError(f"Reg1 is not at the required setpoint (read {value}, need {target})")

    def _verify_other_channels_off(self, target_channel: int) -> None:
        states = self._read(output_state_register(1), 5)
        for index, state in enumerate(states, start=1):
            if index != target_channel and state != 0:
                raise DeviceError(f"non-target channel {index} is on; refusing to open")

    def _verify_channel_setpoints(self, channel) -> None:
        high_addr, _low_addr = freq_registers(channel.channel)
        high, low = self._read(high_addr, 2)
        frequency = (high << 16) | low
        if frequency != channel.frequency_hz:
            raise DeviceError(
                f"channel {channel.channel} frequency mismatch (read {frequency}, config {channel.frequency_hz})"
            )
        duty = self._read(duty_register(channel.channel), 1)[0]
        expected = round(channel.duty_percent * 10)
        if duty != expected:
            raise DeviceError(
                f"channel {channel.channel} duty mismatch (read {duty}, config {expected})"
            )

    # The controller has 5 PWM output-state registers.
    _ALL_CHANNELS = (1, 2, 3, 4, 5)

    def _all_off(self) -> set[int]:
        # Drive EVERY physical channel off (so an energized unconfigured channel
        # can't stay on while we report the laser OFF), but only a CONFIGURED
        # channel's failed read-back counts as a confirmation failure. Unconfigured
        # channels (3-5 are unwired on this rig) must not false-alarm the validated
        # laser-off interlock into manual_wait.
        configured = {ch.channel for ch in (self.config.channels or {}).values()}
        failures: set[int] = set()
        for channel in self._ALL_CHANNELS:
            register = output_state_register(channel)
            try:
                self._write_single(register, 0)
                confirmed = self._read(register, 1)[0] == 0
            except DeviceError:
                confirmed = False
            if not confirmed and channel in configured:
                failures.add(channel)
        return failures

    def _all_off_with_retry(self) -> set[int]:
        # After a de-sync the whole first sweep can fail; flush any stale bytes and
        # retry the full off-sweep once before declaring manual_wait. This is the
        # main "laser won't turn off after one stray byte" self-heal.
        failures = self._all_off()
        if failures:
            self._reset_input_buffer()
            failures = self._all_off()
        return failures

    def _read(self, address: int, count: int) -> list[int]:
        try:
            request = build_read_request(station=self.station, address=address, count=count)
        except ProtocolError as exc:
            raise DeviceError(f"PWM modbus read request invalid: {exc}") from exc
        expected_len = expected_read_response_len(count)

        def attempt() -> list[int]:
            frame = self._exchange(request, expected_len=expected_len)
            try:
                return parse_read_response(frame, station=self.station, function=READ, count=count)
            except ProtocolError as exc:
                raise _ExchangeError(f"PWM modbus read response invalid: {exc}") from exc

        return self._retry_exchange(attempt)

    def _write_single(self, address: int, value: int) -> None:
        try:
            request = build_write_single_request(station=self.station, address=address, value=value)
        except ProtocolError as exc:
            raise DeviceError(f"PWM modbus write request invalid: {exc}") from exc

        def attempt() -> None:
            frame = self._exchange(request, expected_len=8)
            try:
                parse_write_ack(frame, station=self.station, function=WRITE_SINGLE, address=address, value=value)
            except ProtocolError as exc:
                raise _ExchangeError(f"PWM modbus write acknowledgement invalid: {exc}") from exc

        self._retry_exchange(attempt)

    def _retry_exchange(self, attempt):
        # Modbus RTU self-heal: a stale/late byte from a prior timeout desyncs the
        # stream so the response times out or fails to parse. Flush the input buffer
        # and retry the whole exchange ONCE; without this every following exchange
        # (including the 5-channel laser_off sweep) keeps failing and the laser can
        # never be turned off in software. Only ``_ExchangeError`` (read/parse) is
        # retried -- a transport WRITE failure is a plain DeviceError and is not.
        try:
            return attempt()
        except _ExchangeError:
            self._reset_input_buffer()
            return attempt()

    def _reset_input_buffer(self) -> None:
        # Drop late/stray bytes still in the OS buffer before writing a fresh
        # request. getattr-guarded so fakes without the method are a no-op.
        reset = getattr(self.transport, "reset_input_buffer", None)
        if reset is not None:
            reset()

    def _exchange(self, request: bytes, *, expected_len: int) -> bytes:
        self._reset_input_buffer()
        try:
            self.transport.write(request)
        except Exception as exc:  # noqa: BLE001 - write failure is surfaced but never retried
            raise DeviceError(f"PWM modbus write failed: {exc}") from exc
        header = self._read_exact(2)
        if header[1] & 0x80:
            rest = self._read_exact(EXCEPTION_RESPONSE_LEN - 2)
        else:
            rest = self._read_exact(expected_len - 2)
        return header + rest

    def _read_exact(self, n: int) -> bytes:
        deadline = time.monotonic() + PWM_MODBUS_READ_TIMEOUT_S
        buffer = bytearray()
        while len(buffer) < n:
            # Check the deadline every iteration, not only on empty reads, so a slow
            # drip of one byte per read still times out instead of stalling forever.
            if time.monotonic() > deadline:
                raise _ExchangeError("PWM modbus read timed out")
            try:
                chunk = self.transport.read(n - len(buffer))
            except Exception as exc:  # noqa: BLE001
                raise _ExchangeError(f"PWM modbus read failed: {exc}") from exc
            if chunk:
                buffer += chunk
        return bytes(buffer)
