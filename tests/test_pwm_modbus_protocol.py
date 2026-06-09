import pytest

from lab_auto.devices.raw.pwm_modbus import (
    EXCEPTION_RESPONSE_LEN,
    MAX_VOLTAGE_DECIVOLT,
    READ,
    VOLTAGE_REGISTER,
    WRITE_MULTIPLE,
    WRITE_SINGLE,
    ProtocolError,
    build_read_request,
    build_write_multiple_request,
    build_write_single_request,
    build_write_voltage_request,
    crc16,
    duty_register,
    expected_read_response_len,
    freq_registers,
    output_state_register,
    parse_read_response,
    parse_write_ack,
    register_to_voltage,
    voltage_to_register,
)


# --- CRC ---------------------------------------------------------------

def test_crc16_canonical_vector():
    assert crc16(b"\x01\x03\x00\x00\x00\x01") == b"\x84\x0a"


# --- request framing ---------------------------------------------------

def test_build_read_request_frame():
    frame = build_read_request(station=1, address=1, count=1)
    assert frame == bytes.fromhex("010300010001") + crc16(bytes.fromhex("010300010001"))


def test_build_write_single_request_frame():
    body = bytes.fromhex("010600110001")
    assert build_write_single_request(station=1, address=17, value=1) == body + crc16(body)


def test_build_write_multiple_request_frame():
    body = bytes.fromhex("01100002000204000003E8")
    frame = build_write_multiple_request(station=1, address=2, values=[0x0000, 0x03E8])
    assert frame == body + crc16(body)


def test_station_zero_is_rejected():
    with pytest.raises(ProtocolError):
        build_read_request(station=0, address=1, count=1)
    with pytest.raises(ProtocolError):
        build_write_single_request(station=0, address=17, value=1)


def test_forbidden_registers_rejected_on_write():
    for reg in (23, 24, 25):
        with pytest.raises(ProtocolError):
            build_write_single_request(station=1, address=reg, value=1)


# --- voltage codec and cap ---------------------------------------------

def test_voltage_codec():
    assert voltage_to_register(5.0) == 50
    assert register_to_voltage(50) == 5.0
    assert MAX_VOLTAGE_DECIVOLT == 50


def test_voltage_over_cap_rejected():
    with pytest.raises(ProtocolError):
        voltage_to_register(5.1)
    with pytest.raises(ProtocolError):
        build_write_voltage_request(station=1, voltage_v=5.1)


def test_build_write_voltage_request_uses_0x0032():
    frame = build_write_voltage_request(station=1, voltage_v=5.0)
    # station, 0x06, Reg1 = 00 01, value = 00 32
    assert frame[:6] == bytes.fromhex("010600010032")


def test_write_single_to_voltage_register_over_cap_rejected():
    with pytest.raises(ProtocolError):
        build_write_single_request(station=1, address=VOLTAGE_REGISTER, value=51)


# --- register / channel helpers ----------------------------------------

def test_register_helpers():
    assert output_state_register(1) == 17
    assert output_state_register(2) == 18
    assert output_state_register(5) == 21
    assert duty_register(1) == 12
    assert duty_register(5) == 16
    assert freq_registers(1) == (2, 3)
    assert freq_registers(5) == (10, 11)


def test_channel_out_of_range_rejected():
    for bad in (0, 6, -1):
        with pytest.raises(ProtocolError):
            output_state_register(bad)
        with pytest.raises(ProtocolError):
            duty_register(bad)
        with pytest.raises(ProtocolError):
            freq_registers(bad)


# --- read response parsing ---------------------------------------------

def _read_response(station, registers):
    body = bytes([station, READ, len(registers) * 2])
    for reg in registers:
        body += bytes([(reg >> 8) & 0xFF, reg & 0xFF])
    return body + crc16(body)


def test_parse_read_response_returns_registers():
    frame = _read_response(1, [0x0032, 0x0001])
    assert parse_read_response(frame, station=1, function=READ, count=2) == [0x0032, 0x0001]


def test_expected_read_response_len():
    assert expected_read_response_len(1) == 7
    assert expected_read_response_len(5) == 15


def test_parse_read_response_rejects_bad_crc():
    frame = _read_response(1, [0x0001])
    corrupt = frame[:-1] + bytes([frame[-1] ^ 0xFF])
    with pytest.raises(ProtocolError):
        parse_read_response(corrupt, station=1, function=READ, count=1)


def test_parse_read_response_rejects_station_mismatch():
    frame = _read_response(2, [0x0001])
    with pytest.raises(ProtocolError):
        parse_read_response(frame, station=1, function=READ, count=1)


def test_parse_read_response_rejects_function_mismatch():
    frame = _read_response(1, [0x0001])
    with pytest.raises(ProtocolError):
        parse_read_response(frame, station=1, function=WRITE_SINGLE, count=1)


def test_parse_read_response_rejects_exception_reply():
    body = bytes([1, READ | 0x80, 0x02])
    frame = body + crc16(body)
    assert len(frame) == EXCEPTION_RESPONSE_LEN
    with pytest.raises(ProtocolError):
        parse_read_response(frame, station=1, function=READ, count=1)


def test_parse_read_response_rejects_wrong_byte_count():
    body = bytes([1, READ, 4]) + bytes.fromhex("0001")  # claims 4 bytes, supplies 2
    frame = body + crc16(body)
    with pytest.raises(ProtocolError):
        parse_read_response(frame, station=1, function=READ, count=1)


# --- write ack parsing -------------------------------------------------

def test_parse_write_ack_single_ok():
    body = bytes.fromhex("010600110001")
    frame = body + crc16(body)
    parse_write_ack(frame, station=1, function=WRITE_SINGLE, address=17, value=1)


def test_parse_write_ack_multiple_ok():
    body = bytes.fromhex("011000020002")
    frame = body + crc16(body)
    parse_write_ack(frame, station=1, function=WRITE_MULTIPLE, address=2, count=2)


def test_parse_write_ack_rejects_exception():
    body = bytes([1, WRITE_SINGLE | 0x80, 0x03])
    frame = body + crc16(body)
    with pytest.raises(ProtocolError):
        parse_write_ack(frame, station=1, function=WRITE_SINGLE, address=17, value=1)


def test_parse_write_ack_rejects_bad_echo():
    body = bytes.fromhex("010600110000")  # value echoed as 0 instead of 1
    frame = body + crc16(body)
    with pytest.raises(ProtocolError):
        parse_write_ack(frame, station=1, function=WRITE_SINGLE, address=17, value=1)
