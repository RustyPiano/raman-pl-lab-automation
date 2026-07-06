"""Robustness of the PwmModbusLight adapter: RTU de-sync self-heal, read-timeout
deadline, whole-sweep off-retry, and the side-effect-free read/close paths."""

import pytest

from lab_auto.config import LightConfig, PwmChannel
from lab_auto.devices.light import PwmModbusLight
from lab_auto.devices.raw import pwm_modbus as mb
from lab_auto.errors import DeviceError


LASER = PwmChannel(channel=2, frequency_hz=1000, duty_percent=5.0, default_off_required=True)
LED = PwmChannel(channel=1, frequency_hz=1000, duty_percent=5.0, default_off_required=True)

CONFIG = LightConfig(
    type="pwm_modbus",
    manual_light_control=False,
    port="COM7",
    station_id=1,
    baudrate=9600,
    max_output_voltage_v=5.0,
    required_output_voltage_v=5.0,
    channels={"led": LED, "laser": LASER},
)


def _healthy_registers():
    regs = {mb.VOLTAGE_REGISTER: 50}
    for ch in (LASER, LED):
        hi, lo = mb.freq_registers(ch.channel)
        regs[hi] = (ch.frequency_hz >> 16) & 0xFFFF
        regs[lo] = ch.frequency_hz & 0xFFFF
        regs[mb.duty_register(ch.channel)] = round(ch.duty_percent * 10)
        regs[mb.output_state_register(ch.channel)] = 0
    return regs


class _Slave:
    """Correct in-memory RTU slave with an optional first-response corruption and a
    per-register write counter used to simulate a de-sync that clears after a flush."""

    def __init__(self, *, station=1, registers=None, corrupt_writes=(), heal_reg=None, heal_after=0):
        self.station = station
        self.registers = dict(registers or {})
        self.corrupt_writes = set(corrupt_writes)
        self.heal_reg = heal_reg
        self.heal_after = heal_after
        self.reg_writes = 0
        self.writes = 0
        self.resets = 0
        self.closed = False
        self.requests = []
        self._out = bytearray()

    def reset_input_buffer(self):
        self.resets += 1
        self._out.clear()

    def write(self, data: bytes) -> None:
        self.requests.append(bytes(data))
        idx = self.writes
        self.writes += 1
        station, func = data[0], data[1]
        if func == mb.READ:
            addr = (data[2] << 8) | data[3]
            count = (data[4] << 8) | data[5]
            body = bytes([station, func, count * 2])
            for offset in range(count):
                reg = self.registers.get(addr + offset, 0)
                body += bytes([(reg >> 8) & 0xFF, reg & 0xFF])
            frame = body + mb.crc16(body)
        elif func == mb.WRITE_SINGLE:
            addr = (data[2] << 8) | data[3]
            value = (data[4] << 8) | data[5]
            if addr == self.heal_reg:
                self.reg_writes += 1
                if self.reg_writes > self.heal_after:
                    self.registers[addr] = value
            else:
                self.registers[addr] = value
            frame = bytes(data)  # echo
        else:  # pragma: no cover
            raise AssertionError("unexpected function code")
        if idx in self.corrupt_writes:  # flip the last CRC byte, same length
            frame = frame[:-1] + bytes([frame[-1] ^ 0xFF])
        self._out += frame

    def read(self, n: int) -> bytes:
        chunk = bytes(self._out[:n])
        del self._out[:n]
        return chunk

    def close(self):
        self.closed = True


def _adapter(slave):
    return PwmModbusLight(CONFIG, transport=slave, dry_run=False)


# --- de-sync self-heal at the single-exchange level --------------------

def test_read_recovers_after_stale_frame_via_flush_and_retry():
    # First response is corrupt (a stale/late frame de-synced the stream). The
    # adapter must flush the input buffer and retry the whole exchange once.
    slave = _Slave(registers=_healthy_registers(), corrupt_writes={0})
    light = _adapter(slave)

    result = light._read(mb.VOLTAGE_REGISTER, 1)

    assert result == [50]
    assert slave.writes == 2  # original + one retry
    assert slave.resets >= 1  # input buffer flushed before the retry


def test_read_gives_up_after_one_retry():
    # Persistent corruption (both attempts) surfaces as a DeviceError, not an
    # unbounded retry loop.
    slave = _Slave(registers=_healthy_registers(), corrupt_writes={0, 1})
    light = _adapter(slave)

    with pytest.raises(DeviceError):
        light._read(mb.VOLTAGE_REGISTER, 1)
    assert slave.writes == 2


def test_exchange_flushes_input_before_writing_request():
    slave = _Slave(registers=_healthy_registers())
    light = _adapter(slave)

    light._read(mb.VOLTAGE_REGISTER, 1)

    assert slave.resets >= 1  # reset_input_buffer() called before the request write


# --- read-timeout deadline is checked every iteration ------------------

def test_read_exact_times_out_on_slow_byte_drip(monkeypatch):
    import lab_auto.devices.light as light_mod

    clock = {"t": 0.0}

    def fake_monotonic():
        t = clock["t"]
        clock["t"] += 0.4
        return t

    monkeypatch.setattr(light_mod.time, "monotonic", fake_monotonic)

    class DripTransport:
        def read(self, n):
            return b"\x00"  # one byte per read, never completing the frame

    light = PwmModbusLight(CONFIG, transport=DripTransport(), dry_run=False)

    # Deadline must be checked even while bytes keep arriving; otherwise this loops
    # forever. It is raised as DeviceError (via _ExchangeError).
    with pytest.raises(DeviceError, match="timed out"):
        light._read_exact(10)


# --- whole-sweep off-retry --------------------------------------------

def test_laser_off_recovers_when_first_sweep_fails_then_flush_clears():
    # The laser output-state register ignores the first off-write (de-synced sweep)
    # and accepts it only after the sweep-level flush+retry.
    laser_reg = mb.output_state_register(LASER.channel)
    regs = {**_healthy_registers(), laser_reg: 1}
    slave = _Slave(registers=regs, heal_reg=laser_reg, heal_after=1)
    light = _adapter(slave)

    light.laser_off()

    assert light.laser_state == "off_confirmed"
    assert slave.registers[laser_reg] == 0
    assert slave.reg_writes >= 2  # first sweep + retried sweep both wrote the reg


# --- side-effect-free read-back ---------------------------------------

def test_read_hardware_state_reads_registers_without_writing_channels():
    slave = _Slave(registers=_healthy_registers())
    light = _adapter(slave)

    state = light.read_hardware_state()

    assert state["voltage_register"] == 50
    assert state["channel_states"] == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    assert state["laser_state"] == "unknown"
    assert not [f for f in slave.requests if f[1] == mb.WRITE_SINGLE]


def test_read_hardware_state_dry_run_returns_software_state():
    slave = _Slave(registers={})
    light = PwmModbusLight(CONFIG, transport=slave, dry_run=True)

    assert light.read_hardware_state() == {"laser_state": "unknown", "led_state": "unknown"}
    assert slave.requests == []


# --- close(all_off=...) ------------------------------------------------

def test_close_all_off_false_touches_no_channels():
    slave = _Slave(registers=_healthy_registers())
    light = _adapter(slave)

    light.close(all_off=False)

    assert slave.closed is True
    assert not [f for f in slave.requests if f[1] == mb.WRITE_SINGLE]


def test_close_default_drives_channels_off():
    slave = _Slave(registers={**_healthy_registers(), mb.output_state_register(LASER.channel): 1})
    light = _adapter(slave)

    light.close()

    assert slave.closed is True
    assert slave.registers[mb.output_state_register(LASER.channel)] == 0


# --- safety_reset ------------------------------------------------------

def test_safety_reset_drives_all_channels_off():
    slave = _Slave(registers={**_healthy_registers(), mb.output_state_register(LASER.channel): 1})
    light = _adapter(slave)

    light.safety_reset()

    assert light.laser_state == "off_confirmed"
    assert light.led_state == "off_confirmed"
    for ch in (1, 2, 3, 4, 5):
        assert slave.registers[mb.output_state_register(ch)] == 0


def test_safety_reset_raises_when_channel_cannot_be_confirmed_off():
    laser_reg = mb.output_state_register(LASER.channel)

    class StuckSlave(_Slave):
        def write(self, data):  # ignore the laser off-write so read-back stays 1
            if data[1] == mb.WRITE_SINGLE and ((data[2] << 8) | data[3]) == laser_reg:
                self.requests.append(bytes(data))
                self.writes += 1
                self._out += bytes(data)
                return
            super().write(data)

    slave = StuckSlave(registers={**_healthy_registers(), laser_reg: 1})
    light = _adapter(slave)

    with pytest.raises(DeviceError, match="safety reset"):
        light.safety_reset()
    assert light.laser_state == "manual_wait"


def test_safety_reset_dry_run_marks_off_without_io():
    slave = _Slave(registers={})
    light = PwmModbusLight(CONFIG, transport=slave, dry_run=True)

    light.safety_reset()

    assert light.laser_state == "off_confirmed"
    assert slave.requests == []
