import pytest

from lab_auto.config import LightConfig, PwmChannel
from lab_auto.devices.light import PwmModbusLight
from lab_auto.devices.raw import pwm_modbus as mb
from lab_auto.errors import DeviceError


# --- in-memory modbus slave -------------------------------------------

class FakeModbusSlave:
    """Minimal correct Modbus RTU slave over a write()/read(n) byte transport."""

    def __init__(self, *, station=1, registers=None, ignore_writes_to=(), fault=None):
        self.station = station
        self.registers = dict(registers or {})
        self.ignore_writes_to = set(ignore_writes_to)
        self.fault = fault
        self._out = bytearray()
        self.requests = []  # recorded request frames

    def write(self, data: bytes) -> None:
        self.requests.append(bytes(data))
        if self.fault is not None:
            self._out += self.fault(bytes(data))
            return
        station, func = data[0], data[1]
        if func == mb.READ:
            addr = (data[2] << 8) | data[3]
            count = (data[4] << 8) | data[5]
            body = bytes([station, func, count * 2])
            for offset in range(count):
                reg = self.registers.get(addr + offset, 0)
                body += bytes([(reg >> 8) & 0xFF, reg & 0xFF])
            self._out += body + mb.crc16(body)
        elif func == mb.WRITE_SINGLE:
            addr = (data[2] << 8) | data[3]
            value = (data[4] << 8) | data[5]
            if addr not in self.ignore_writes_to:
                self.registers[addr] = value
            self._out += bytes(data)  # echo request
        elif func == mb.WRITE_MULTIPLE:
            addr = (data[2] << 8) | data[3]
            count = (data[4] << 8) | data[5]
            body = bytes([station, func, data[2], data[3], data[4], data[5]])
            self._out += body + mb.crc16(body)
        else:  # pragma: no cover - unused
            raise AssertionError("unexpected function code")

    def read(self, n: int) -> bytes:
        chunk = bytes(self._out[:n])
        del self._out[:n]
        return chunk


# --- config + happy-path register fixtures ----------------------------

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
    regs = {mb.VOLTAGE_REGISTER: 50}  # Reg1 = 0x0032
    for ch in (LASER, LED):
        hi, lo = mb.freq_registers(ch.channel)
        regs[hi] = (ch.frequency_hz >> 16) & 0xFFFF
        regs[lo] = ch.frequency_hz & 0xFFFF
        regs[mb.duty_register(ch.channel)] = round(ch.duty_percent * 10)
        regs[mb.output_state_register(ch.channel)] = 0
    return regs


def _adapter(slave):
    return PwmModbusLight(CONFIG, transport=slave, dry_run=False)


# --- interface parity --------------------------------------------------

def test_workflow_interface_methods_present():
    light = _adapter(FakeModbusSlave(registers=_healthy_registers()))
    assert light.require_off_confirmation() == "laser_off"
    assert light.require_on_confirmation() == "laser_on"
    assert light.get_state() == {"laser_state": "unknown", "led_state": "unknown"}


# --- laser on happy path ----------------------------------------------

def test_laser_on_happy_path_sets_on_confirmed():
    slave = FakeModbusSlave(registers=_healthy_registers())
    light = _adapter(slave)
    light.laser_on()
    assert light.laser_state == "on_confirmed"
    # output state register for laser channel was driven to 1
    assert slave.registers[mb.output_state_register(LASER.channel)] == 1


def test_confirm_laser_on_drives_laser_on():
    slave = FakeModbusSlave(registers=_healthy_registers())
    light = _adapter(slave)
    light.confirm_laser_on(require_confirmation=False)
    assert light.laser_state == "on_confirmed"


# --- readback / safety refusals ---------------------------------------

def test_laser_on_refuses_if_output_state_readback_not_one():
    slave = FakeModbusSlave(
        registers=_healthy_registers(),
        ignore_writes_to={mb.output_state_register(LASER.channel)},
    )
    light = _adapter(slave)
    with pytest.raises(DeviceError):
        light.laser_on()
    assert light.laser_state != "on_confirmed"


def test_laser_on_refuses_if_voltage_not_setpoint():
    regs = _healthy_registers()
    regs[mb.VOLTAGE_REGISTER] = 40  # 4.0 V, not 0x0032
    light = _adapter(FakeModbusSlave(registers=regs))
    with pytest.raises(DeviceError):
        light.laser_on()
    assert light.laser_state != "on_confirmed"


def test_laser_on_refuses_if_other_channel_on():
    regs = _healthy_registers()
    regs[mb.output_state_register(LED.channel)] = 1  # non-target channel already on
    light = _adapter(FakeModbusSlave(registers=regs))
    with pytest.raises(DeviceError):
        light.laser_on()
    assert light.laser_state != "on_confirmed"


def test_laser_on_refuses_on_frequency_mismatch():
    regs = _healthy_registers()
    hi, lo = mb.freq_registers(LASER.channel)
    regs[lo] = 999  # config expects 1000
    light = _adapter(FakeModbusSlave(registers=regs))
    with pytest.raises(DeviceError):
        light.laser_on()


def test_laser_on_refuses_on_duty_mismatch():
    regs = _healthy_registers()
    regs[mb.duty_register(LASER.channel)] = 40  # config expects 50 (5.0%)
    light = _adapter(FakeModbusSlave(registers=regs))
    with pytest.raises(DeviceError):
        light.laser_on()


# --- Reg1 write precondition ------------------------------------------

def test_ensure_voltage_setpoint_refuses_when_channel_on():
    regs = _healthy_registers()
    regs[mb.VOLTAGE_REGISTER] = 0
    regs[mb.output_state_register(LED.channel)] = 1
    light = _adapter(FakeModbusSlave(registers=regs))
    with pytest.raises(DeviceError):
        light.ensure_voltage_setpoint()


def test_ensure_voltage_setpoint_writes_when_all_off():
    regs = _healthy_registers()
    regs[mb.VOLTAGE_REGISTER] = 0
    slave = FakeModbusSlave(registers=regs)
    light = _adapter(slave)
    light.ensure_voltage_setpoint()
    assert slave.registers[mb.VOLTAGE_REGISTER] == 50


def test_ensure_voltage_setpoint_refuses_on_reg1_readback_mismatch():
    # Reg1 (0x0032 = 5.0 V) must be confirmed by read-back, not just written.
    regs = _healthy_registers()
    regs[mb.VOLTAGE_REGISTER] = 0
    slave = FakeModbusSlave(registers=regs, ignore_writes_to={mb.VOLTAGE_REGISTER})
    light = _adapter(slave)
    with pytest.raises(DeviceError):
        light.ensure_voltage_setpoint()


# --- LED isolation -----------------------------------------------------

def test_led_on_sets_led_state_only():
    slave = FakeModbusSlave(registers=_healthy_registers())
    light = _adapter(slave)
    light.led_on()
    assert light.led_state == "on_confirmed"
    assert light.laser_state == "unknown"  # never satisfies the laser precondition


# --- off / failure path ------------------------------------------------

def test_laser_off_confirms_all_channels_off():
    regs = _healthy_registers()
    regs[mb.output_state_register(LASER.channel)] = 1
    slave = FakeModbusSlave(registers=regs)
    light = _adapter(slave)
    light.laser_off()
    assert light.laser_state == "off_confirmed"
    assert slave.registers[mb.output_state_register(LASER.channel)] == 0


def test_laser_off_with_build_side_error_enters_manual_wait():
    # defense in depth: even a frame-builder error (e.g. bad station) on the off
    # path must surface as DeviceError and force manual confirmation, not leak.
    bad_config = LightConfig(
        type="pwm_modbus",
        manual_light_control=False,
        port="COM7",
        station_id=0,  # build_read/write_request will raise ProtocolError
        baudrate=9600,
        max_output_voltage_v=5.0,
        required_output_voltage_v=5.0,
        channels={"laser": LASER},
    )
    light = PwmModbusLight(bad_config, transport=FakeModbusSlave(registers={}), dry_run=False)
    with pytest.raises(DeviceError):
        light.laser_off()
    assert light.laser_state == "manual_wait"


def test_laser_off_readback_failure_requires_manual():
    slave = FakeModbusSlave(
        registers={**_healthy_registers(), mb.output_state_register(LASER.channel): 1},
        ignore_writes_to={mb.output_state_register(LASER.channel)},
    )
    light = _adapter(slave)
    with pytest.raises(DeviceError):
        light.laser_off()
    assert light.laser_state == "manual_wait"


# --- forbidden writes / station 0 --------------------------------------

def test_never_writes_forbidden_registers_or_station_zero():
    slave = FakeModbusSlave(registers=_healthy_registers())
    light = _adapter(slave)
    light.laser_on()
    light.laser_off()
    for frame in slave.requests:
        assert frame[0] != 0  # station id never 0
        if frame[1] in (mb.WRITE_SINGLE, mb.WRITE_MULTIPLE):
            addr = (frame[2] << 8) | frame[3]
            assert addr not in mb.FORBIDDEN_REGISTERS


# --- read-back validity errors propagate -------------------------------

def test_bad_crc_response_raises_device_error():
    def fault(_request):
        body = bytes([1, mb.READ, 2, 0x00, 0x32])
        good = body + mb.crc16(body)
        return good[:-1] + bytes([good[-1] ^ 0xFF])  # corrupt CRC

    light = _adapter(FakeModbusSlave(fault=fault))
    with pytest.raises(DeviceError):
        light.laser_on()


def test_exception_response_raises_device_error():
    def fault(_request):
        body = bytes([1, mb.READ | 0x80, 0x02])
        return body + mb.crc16(body)

    light = _adapter(FakeModbusSlave(fault=fault))
    with pytest.raises(DeviceError):
        light.laser_on()


# --- dry-run -----------------------------------------------------------

def test_dry_run_performs_no_io():
    slave = FakeModbusSlave(registers={})
    light = PwmModbusLight(CONFIG, transport=slave, dry_run=True)
    light.laser_on()
    light.laser_off()
    light.led_on()
    assert slave.requests == []
    assert light.laser_state == "off_confirmed"
