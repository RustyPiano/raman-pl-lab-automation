import pytest

from lab_auto.devices.raw.waynelabs_protocol import (
    Completed,
    LimitOrHome,
    ProtocolError,
    build_home_command,
    build_identify_command,
    build_move_command,
    build_trigger_command,
    parse_device_info,
    parse_completion,
    split_steps,
)


def test_build_x_positive_move_command():
    assert build_move_command(axis="x", steps=924, speed=0, direction="positive") == "?X00924c"


def test_build_x_negative_move_command():
    assert build_move_command(axis="x", steps=924, speed=0, direction="negative") == "?X00924b"


def test_build_home_command_uses_zero_steps():
    assert build_home_command(axis="z", speed=8, direction="negative") == "?X80000f"


def test_build_identify_command_uses_unified_query():
    assert build_identify_command() == "?S000000"


def test_build_open_loop_trigger_command():
    assert build_trigger_command(mode="open_loop") == "?X11111q"


def test_parse_device_info_identifies_linear_stage():
    info = parse_device_info("?XV09240426\r".ljust(45, "0"))

    assert info.device_code == "X"
    assert info.device_type == "waynelabs_linear"


def test_split_steps_limits_single_command_to_9999():
    assert split_steps(25000) == [9999, 9999, 5002]


def test_parse_completion_accepts_direction_response():
    assert parse_completion("?b") == Completed(direction="b")


def test_parse_completion_accepts_limit_or_home():
    assert parse_completion("?t") == LimitOrHome()


def test_rejects_invalid_speed():
    with pytest.raises(ProtocolError, match="speed"):
        build_move_command(axis="x", steps=1, speed=12, direction="positive")
