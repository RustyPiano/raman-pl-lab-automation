"""Raw Modbus RTU framing for the multi-channel PWM signal generator.

This module owns every protocol detail: CRC16, function codes, register numbers,
the 5.0 V hard cap, and byte-level frame build/parse. It performs no I/O and
imports neither ``serial`` nor ``time``. Adapters call these helpers; nothing
above this layer hand-writes Modbus bytes.

Register map (spec 6.5):
- Reg0          reserved, read-only.
- Reg1          global output voltage, unit 0.1 V (hard max 5.0 V == 50 == 0x0032).
- Reg2-Reg11    CH1-CH5 frequency, per channel (hi << 16 | lo), 32-bit Hz.
- Reg12-Reg16   CH1-CH5 duty, unit 0.1 %.
- Reg17-Reg21   CH1-CH5 output state, 0 = off, 1 = on.
- Reg22         current display channel.
- Reg23-Reg25   key-lock / baud / undefined -- forbidden to write.
"""

import math
from dataclasses import dataclass


class ProtocolError(ValueError):
    pass


READ = 0x03
WRITE_SINGLE = 0x06
WRITE_MULTIPLE = 0x10

VOLTAGE_REGISTER = 1
MAX_VOLTAGE_DECIVOLT = 50  # 5.0 V == 0x0032
FORBIDDEN_REGISTERS = frozenset({0, 23, 24, 25})  # Reg0 reserved/read-only; 23-25 protected
EXCEPTION_RESPONSE_LEN = 5

_MIN_CHANNEL = 1
_MAX_CHANNEL = 5
_MAX_STATION = 247


def crc16(payload: bytes) -> bytes:
    """Modbus CRC16 (poly 0xA001, init 0xFFFF), appended low byte first."""
    crc = 0xFFFF
    for byte in payload:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF])


def _frame(body: bytes) -> bytes:
    return body + crc16(body)


def _validate_station(station: int) -> int:
    if isinstance(station, bool) or not isinstance(station, int):
        raise ProtocolError("station_id must be an integer")
    if station < 1 or station > _MAX_STATION:
        raise ProtocolError("station_id must be between 1 and 247 (0 is forbidden)")
    return station


def _validate_register(address: int) -> int:
    if isinstance(address, bool) or not isinstance(address, int):
        raise ProtocolError("register address must be an integer")
    if address < 0 or address > 0xFFFF:
        raise ProtocolError("register address out of range")
    return address


def _validate_word(value: int, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProtocolError(f"{field} must be an integer")
    if value < 0 or value > 0xFFFF:
        raise ProtocolError(f"{field} must fit a 16-bit register")
    return value


def _validate_channel(channel: int) -> int:
    if isinstance(channel, bool) or not isinstance(channel, int):
        raise ProtocolError("channel must be an integer")
    if channel < _MIN_CHANNEL or channel > _MAX_CHANNEL:
        raise ProtocolError("channel must be between 1 and 5")
    return channel


# --- channel/register helpers ------------------------------------------

def output_state_register(channel: int) -> int:
    return 16 + _validate_channel(channel)


def duty_register(channel: int) -> int:
    return 11 + _validate_channel(channel)


def freq_registers(channel: int) -> tuple[int, int]:
    channel = _validate_channel(channel)
    high = 2 * channel
    return (high, high + 1)


# --- voltage codec ------------------------------------------------------

def voltage_to_register(voltage_v: float) -> int:
    if isinstance(voltage_v, bool) or not isinstance(voltage_v, (int, float)):
        raise ProtocolError("voltage must be a number")
    scaled = float(voltage_v) * 10
    if not math.isfinite(scaled):
        raise ProtocolError("voltage must be finite")
    if scaled < 0:
        raise ProtocolError("voltage must be non-negative")
    # Enforce the hard cap before rounding so e.g. 5.04 V cannot round down to 5.0.
    if scaled > MAX_VOLTAGE_DECIVOLT:
        raise ProtocolError("voltage exceeds the 5.0 V hard cap")
    return round(scaled)


def register_to_voltage(register_value: int) -> float:
    return _validate_word(register_value, field="voltage register") / 10.0


# --- request builders ---------------------------------------------------

def build_read_request(*, station: int, address: int, count: int) -> bytes:
    _validate_station(station)
    _validate_register(address)
    if isinstance(count, bool) or not isinstance(count, int) or count < 1 or count > 125:
        raise ProtocolError("read count must be between 1 and 125")
    body = bytes(
        [station, READ, (address >> 8) & 0xFF, address & 0xFF, (count >> 8) & 0xFF, count & 0xFF]
    )
    return _frame(body)


def build_write_single_request(*, station: int, address: int, value: int) -> bytes:
    _validate_station(station)
    _validate_register(address)
    _validate_word(value, field="value")
    if address in FORBIDDEN_REGISTERS:
        raise ProtocolError(f"register {address} is forbidden to write")
    if address == VOLTAGE_REGISTER and value > MAX_VOLTAGE_DECIVOLT:
        raise ProtocolError("voltage register write exceeds the 5.0 V hard cap")
    body = bytes(
        [station, WRITE_SINGLE, (address >> 8) & 0xFF, address & 0xFF, (value >> 8) & 0xFF, value & 0xFF]
    )
    return _frame(body)


def build_write_multiple_request(*, station: int, address: int, values: list[int]) -> bytes:
    _validate_station(station)
    _validate_register(address)
    if not values:
        raise ProtocolError("write-multiple requires at least one value")
    count = len(values)
    if count > 123:  # Modbus 0x10 caps at 123 registers; also keeps byte-count in one byte
        raise ProtocolError("write-multiple supports at most 123 registers")
    _validate_register(address + count - 1)  # reject writes spilling past the register map
    for offset in range(count):
        target = address + offset
        _validate_word(values[offset], field="value")  # validate before any comparison
        if target in FORBIDDEN_REGISTERS:
            raise ProtocolError(f"register {target} is forbidden to write")
        if target == VOLTAGE_REGISTER and values[offset] > MAX_VOLTAGE_DECIVOLT:
            raise ProtocolError("voltage register write exceeds the 5.0 V hard cap")
    data = bytearray()
    for value in values:
        data += bytes([(value >> 8) & 0xFF, value & 0xFF])
    body = bytes(
        [station, WRITE_MULTIPLE, (address >> 8) & 0xFF, address & 0xFF, (count >> 8) & 0xFF, count & 0xFF, len(data)]
    ) + bytes(data)
    return _frame(body)


def build_write_voltage_request(*, station: int, voltage_v: float) -> bytes:
    value = voltage_to_register(voltage_v)
    return build_write_single_request(station=station, address=VOLTAGE_REGISTER, value=value)


def expected_read_response_len(count: int) -> int:
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise ProtocolError("count must be a positive integer")
    return 5 + 2 * count


# --- response parsers ---------------------------------------------------

def _check_frame(frame: bytes, *, station: int, function: int) -> None:
    if len(frame) < EXCEPTION_RESPONSE_LEN:
        raise ProtocolError("response frame is too short")
    if crc16(frame[:-2]) != frame[-2:]:
        raise ProtocolError("response CRC mismatch")
    if frame[0] != station:
        raise ProtocolError("response station mismatch")
    func = frame[1]
    if func & 0x80:
        code = frame[2] if len(frame) > 2 else -1
        raise ProtocolError(f"modbus exception response: function={func:#04x} code={code}")
    if func != function:
        raise ProtocolError("response function-code mismatch")


def parse_read_response(frame: bytes, *, station: int, function: int, count: int) -> list[int]:
    _validate_station(station)
    _check_frame(frame, station=station, function=function)
    byte_count = frame[2]
    if byte_count != 2 * count:
        raise ProtocolError("response byte count does not match requested register count")
    if len(frame) != 3 + byte_count + 2:
        raise ProtocolError("response length inconsistent with byte count")
    registers = []
    for index in range(count):
        high = frame[3 + 2 * index]
        low = frame[4 + 2 * index]
        registers.append((high << 8) | low)
    return registers


def parse_write_ack(
    frame: bytes,
    *,
    station: int,
    function: int,
    address: int,
    value: int | None = None,
    count: int | None = None,
) -> None:
    _validate_station(station)
    _check_frame(frame, station=station, function=function)
    if len(frame) != 8:
        raise ProtocolError("write acknowledgement must be 8 bytes")
    echo_address = (frame[2] << 8) | frame[3]
    if echo_address != address:
        raise ProtocolError("write acknowledgement address mismatch")
    tail = (frame[4] << 8) | frame[5]
    if function == WRITE_SINGLE:
        if value is not None and tail != value:
            raise ProtocolError("write-single value echo mismatch")
    elif function == WRITE_MULTIPLE:
        if count is not None and tail != count:
            raise ProtocolError("write-multiple quantity mismatch")
    else:
        raise ProtocolError("unsupported write function code")


class PwmModbusProtocol:
    """Thin object wrapper, mirroring WaynelabsRawProtocol."""

    crc16 = staticmethod(crc16)

    def build_read_request(self, *, station: int, address: int, count: int) -> bytes:
        return build_read_request(station=station, address=address, count=count)

    def build_write_single_request(self, *, station: int, address: int, value: int) -> bytes:
        return build_write_single_request(station=station, address=address, value=value)

    def build_write_multiple_request(self, *, station: int, address: int, values: list[int]) -> bytes:
        return build_write_multiple_request(station=station, address=address, values=values)

    def build_write_voltage_request(self, *, station: int, voltage_v: float) -> bytes:
        return build_write_voltage_request(station=station, voltage_v=voltage_v)

    def parse_read_response(self, frame: bytes, *, station: int, function: int, count: int) -> list[int]:
        return parse_read_response(frame, station=station, function=function, count=count)

    def parse_write_ack(self, frame: bytes, **kwargs) -> None:
        return parse_write_ack(frame, **kwargs)
