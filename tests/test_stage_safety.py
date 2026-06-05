from dataclasses import replace

import pytest

from lab_auto.config import StageConfig
from lab_auto.devices.waynelabs_stage import AxisState, PositionLedger, WaynelabsStage
from lab_auto.errors import DeviceError, SafetyError


def config(tmp_path):
    return StageConfig(
        type="waynelabs_linear",
        port="COM5",
        baudrate=9600,
        resolution_um={"x": 0.04, "y": 0.04, "z": 0.04},
        default_speed=8,
        soft_limits_um={"x": [-5000, 5000], "y": [-5000, 5000], "z": [-1000, 1000]},
        state_file=tmp_path / "stage_position.json",
        max_unknown_move_um=100,
    )


def test_unknown_axis_allows_small_move(tmp_path):
    protocol = FakeStageProtocol()
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True, protocol=protocol)

    actions = stage.move_relative(axis="x", um=10, speed=8)

    assert actions == ["encoded-move"]
    assert protocol.moves == [{"axis": "x", "steps": 250, "speed": 8, "direction": "positive"}]


def test_real_move_rejects_unsupported_stage_type_before_writing(tmp_path):
    cfg = replace(config(tmp_path), type="waynelabs_filter_wheel")
    transport = FakeTransport(["?c"])
    stage = WaynelabsStage(cfg, transport=transport, dry_run=False)

    with pytest.raises(DeviceError, match="linear"):
        stage.move_relative(axis="x", um=10, speed=8)

    assert transport.writes == []


def test_unknown_axis_rejects_large_move(tmp_path):
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True)

    with pytest.raises(SafetyError, match="unknown position"):
        stage.move_relative(axis="x", um=150, speed=8)


def test_known_axis_uses_soft_limits(tmp_path):
    ledger = PositionLedger(states={"x": AxisState.USER_ZEROED}, position_um={"x": 4995.0})
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True, ledger=ledger)

    with pytest.raises(SafetyError, match="soft limit"):
        stage.move_relative(axis="x", um=10, speed=8)


def test_known_axis_updates_position_after_successful_move(tmp_path):
    ledger = PositionLedger(states={"x": AxisState.USER_ZEROED}, position_um={"x": 100.0})
    stage = WaynelabsStage(config(tmp_path), transport=FakeTransport(["?c"]), dry_run=False, ledger=ledger)

    stage.move_relative(axis="x", um=10, speed=8)

    assert ledger.position_um["x"] == 110.0


def test_home_marks_axis_homed_after_success(tmp_path):
    ledger = PositionLedger()
    stage = WaynelabsStage(config(tmp_path), transport=FakeTransport(["?t"]), dry_run=False, ledger=ledger)

    actions = stage.home(axis="x", direction="negative", speed=8)

    assert actions == ["?X80000b"]
    assert ledger.states["x"] is AxisState.HOMED
    assert ledger.position_um["x"] == 0.0


def test_real_move_rejects_limit_response_without_updating_known_position(tmp_path):
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 10.0})
    stage = WaynelabsStage(config(tmp_path), transport=FakeTransport(["?t"]), dry_run=False, ledger=ledger)

    with pytest.raises(DeviceError, match="limit"):
        stage.move_relative(axis="x", um=10, speed=8)

    assert ledger.position_um["x"] == 10.0


def test_real_move_marks_axis_unknown_after_bad_completion(tmp_path):
    cfg = config(tmp_path)
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 10.0})
    stage = WaynelabsStage(cfg, transport=FakeTransport(["bad"]), dry_run=False, ledger=ledger)

    with pytest.raises(DeviceError, match="unexpected"):
        stage.move_relative(axis="x", um=10, speed=8)

    loaded = PositionLedger.load(cfg)
    assert ledger.states["x"] is AxisState.UNKNOWN
    assert loaded.states["x"] is AxisState.UNKNOWN


def test_real_home_requires_limit_or_home_completion(tmp_path):
    ledger = PositionLedger()
    stage = WaynelabsStage(config(tmp_path), transport=FakeTransport(["?b"]), dry_run=False, ledger=ledger)

    with pytest.raises(DeviceError, match="home"):
        stage.home(axis="x", direction="negative", speed=8)

    assert ledger.states["x"] is AxisState.UNKNOWN


def test_home_persists_stage_state_file(tmp_path):
    cfg = config(tmp_path)
    ledger = PositionLedger()
    stage = WaynelabsStage(cfg, transport=FakeTransport(["?t"]), dry_run=False, ledger=ledger)

    stage.home(axis="x", direction="negative", speed=8)
    loaded = PositionLedger.load(cfg)

    assert loaded.states["x"] is AxisState.HOMED
    assert loaded.position_um["x"] == 0.0


def test_dry_run_home_does_not_persist_or_mark_homed(tmp_path):
    cfg = config(tmp_path)
    stage = WaynelabsStage(cfg, transport=None, dry_run=True)

    stage.home(axis="x", direction="negative", speed=8)

    assert stage.ledger.states["x"] is AxisState.UNKNOWN
    assert not cfg.state_file.exists()


def test_dry_run_known_axis_move_does_not_persist_position(tmp_path):
    cfg = config(tmp_path)
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 10.0})
    stage = WaynelabsStage(cfg, transport=None, dry_run=True, ledger=ledger)

    stage.move_relative(axis="x", um=10, speed=8)

    assert ledger.position_um["x"] == 10.0
    assert not cfg.state_file.exists()


def test_identify_validates_real_device_response(tmp_path):
    transport = FakeTransport(["?XV09240426\r".ljust(45, "0")])
    stage = WaynelabsStage(config(tmp_path), transport=transport, dry_run=False)

    result = stage.identify()

    assert transport.writes == [b"?S000000"]
    assert result["device_code"] == "X"
    assert result["type"] == "waynelabs_linear"


def test_identify_drains_multiline_device_response_before_next_move(tmp_path):
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 0.0})
    transport = FakeTransport(["?XV09240426\r", "X200101111\r", "Y200101111\r", "Z411001011\r", "?c"])
    stage = WaynelabsStage(config(tmp_path), transport=transport, dry_run=False, ledger=ledger)

    stage.identify()
    stage.move_relative(axis="x", um=10, speed=8)

    assert transport.writes == [b"?S000000", b"?X80250c"]
    assert ledger.position_um["x"] == 10.0


def test_trigger_sends_open_loop_command(tmp_path):
    transport = FakeTransport(["?q"])
    stage = WaynelabsStage(config(tmp_path), transport=transport, dry_run=False)

    actions = stage.trigger(mode="open_loop")

    assert actions == ["?X11111q"]
    assert transport.writes == [b"?X11111q"]


class FakeStageProtocol:
    def __init__(self):
        self.moves = []

    def split_steps(self, steps: int) -> list[int]:
        return [steps]

    def build_move_command(self, *, axis: str, steps: int, speed: int, direction: str) -> str:
        self.moves.append({"axis": axis, "steps": steps, "speed": speed, "direction": direction})
        return "encoded-move"

    def build_home_command(self, *, axis: str, speed: int, direction: str) -> str:
        return "encoded-home"


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.writes = []

    def write(self, data: bytes):
        self.writes.append(data)

    def readline(self):
        if not self.responses:
            return b""
        return self.responses.pop(0).encode("ascii")

    def close(self):
        pass
