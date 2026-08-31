from dataclasses import replace

import pytest

from lab_auto.config import StageConfig
from lab_auto.devices.waynelabs_stage import AxisState, PositionLedger, WaynelabsStage
from lab_auto.errors import ConfigError, DeviceError, SafetyError


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
        home_direction={"x": "negative", "y": "negative", "z": "positive"},
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


def test_stage_move_rejects_huge_integer_distance_as_config_error(tmp_path):
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True)

    with pytest.raises(ConfigError, match="move distance"):
        stage.move_relative(axis="x", um=10**400, speed=8)


def test_stage_move_rejects_finite_distance_that_overflows_steps(tmp_path):
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True)

    with pytest.raises(ConfigError, match="steps"):
        stage.move_relative(axis="x", um=1e308, speed=8)


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


def test_known_axis_updates_position_by_commanded_step_distance(tmp_path):
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 100.0})
    stage = WaynelabsStage(config(tmp_path), transport=FakeTransport(["?c"]), dry_run=False, ledger=ledger)

    actions = stage.move_relative(axis="x", um=0.05, speed=8)

    assert actions == ["?X80001c"]
    assert ledger.position_um["x"] == 100.04


def test_known_axis_rejects_move_when_commanded_steps_exceed_soft_limit(tmp_path):
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 4999.97})
    stage = WaynelabsStage(config(tmp_path), transport=FakeTransport(["?c"]), dry_run=False, ledger=ledger)

    with pytest.raises(SafetyError, match="soft limit"):
        stage.move_relative(axis="x", um=0.03, speed=8)

    assert stage.transport.writes == []
    assert ledger.position_um["x"] == 4999.97


def test_nonzero_move_that_rounds_to_zero_steps_is_rejected(tmp_path):
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True)

    with pytest.raises(ConfigError, match="steps"):
        stage.move_relative(axis="x", um=0.01, speed=8)


def test_home_marks_axis_homed_after_success(tmp_path):
    ledger = PositionLedger()
    stage = WaynelabsStage(config(tmp_path), transport=FakeTransport(["?t"]), dry_run=False, ledger=ledger)

    actions = stage.home(axis="x", direction="negative", speed=8)

    assert actions == ["?X80000b"]
    assert ledger.states["x"] is AxisState.HOMED
    assert ledger.position_um["x"] == 0.0


def test_home_waits_across_read_timeouts_until_home_marker(tmp_path):
    ledger = PositionLedger()
    transport = FakeTransport(["", "?t"])
    stage = WaynelabsStage(config(tmp_path), transport=transport, dry_run=False, ledger=ledger)

    stage.home(axis="x", direction="negative", speed=8)

    assert ledger.states["x"] is AxisState.HOMED
    assert transport.reads >= 2


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


def test_real_move_marks_axis_unknown_after_transport_read_error(tmp_path):
    cfg = config(tmp_path)
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 10.0})
    transport = ReadErrorTransport()
    stage = WaynelabsStage(cfg, transport=transport, dry_run=False, ledger=ledger)

    with pytest.raises(DeviceError, match="serial read"):
        stage.move_relative(axis="x", um=10, speed=8)

    loaded = PositionLedger.load(cfg)
    assert transport.writes == [b"?X80250c"]
    assert ledger.states["x"] is AxisState.UNKNOWN
    assert loaded.states["x"] is AxisState.UNKNOWN


def test_real_move_rejects_extra_completion_marker_after_success(tmp_path):
    cfg = config(tmp_path)
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 10.0})
    stage = WaynelabsStage(cfg, transport=FakeTransport(["?c", "?b"]), dry_run=False, ledger=ledger)

    with pytest.raises(DeviceError, match="trailing"):
        stage.move_relative(axis="x", um=10, speed=8)

    loaded = PositionLedger.load(cfg)
    assert ledger.states["x"] is AxisState.UNKNOWN
    assert loaded.states["x"] is AxisState.UNKNOWN
    assert ledger.position_um["x"] == 10.0


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


def test_corrupt_persisted_nan_position_resets_ledger(tmp_path):
    cfg = config(tmp_path)
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_file.write_text(
        """
{
  "states": {"x": "homed", "y": "unknown", "z": "unknown"},
  "position_um": {"x": NaN, "y": 0.0, "z": 0.0},
  "resolution_um": {"x": 0.04, "y": 0.04, "z": 0.04},
  "device_identity": {"type": "waynelabs_linear", "port": "COM5"}
}
""",
        encoding="utf-8",
    )

    loaded = PositionLedger.load(cfg)

    assert loaded.states["x"] is AxisState.UNKNOWN


def test_corrupt_persisted_missing_known_position_resets_ledger(tmp_path):
    cfg = config(tmp_path)
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_file.write_text(
        """
{
  "states": {"x": "homed", "y": "unknown", "z": "unknown"},
  "position_um": {"y": 0.0, "z": 0.0},
  "resolution_um": {"x": 0.04, "y": 0.04, "z": 0.04},
  "device_identity": {"type": "waynelabs_linear", "port": "COM5"}
}
""",
        encoding="utf-8",
    )

    loaded = PositionLedger.load(cfg)

    assert loaded.states["x"] is AxisState.UNKNOWN


@pytest.mark.parametrize("position_um", [{}, {"x": float("nan")}])
def test_known_axis_with_missing_or_nonfinite_runtime_position_fails_closed(tmp_path, position_um):
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um=position_um)
    transport = FakeTransport(["?c"])
    stage = WaynelabsStage(config(tmp_path), transport=transport, dry_run=False, ledger=ledger)

    with pytest.raises(SafetyError, match="position"):
        stage.move_relative(axis="x", um=10, speed=8)

    assert transport.writes == []


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


def test_identify_waits_across_read_timeouts_for_first_response(tmp_path):
    transport = FakeTransport(["", "?XV09240426\r".ljust(45, "0")])
    stage = WaynelabsStage(config(tmp_path), transport=transport, dry_run=False)

    result = stage.identify()

    assert result["device_code"] == "X"
    assert transport.reads >= 2


def test_identify_drains_multiline_device_response_before_next_move(tmp_path):
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 0.0})
    transport = FakeTransport(["?XV09240426\r", "X200101111\r", "Y200101111\r", "Z411001011\r", "?c"])
    stage = WaynelabsStage(config(tmp_path), transport=transport, dry_run=False, ledger=ledger)

    stage.identify()
    stage.move_relative(axis="x", um=10, speed=8)

    assert transport.writes == [b"?S000000", b"?X80250c"]
    assert ledger.position_um["x"] == 10.0


def test_identify_drains_multiline_response_across_empty_reads_before_next_move(tmp_path):
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 0.0})
    transport = FakeTransport(["?XV09240426\r", "", "X200101111\r", "Y200101111\r", "Z411001011\r", "", "?c"])
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


def test_closed_loop_trigger_ignores_intermediate_prompt_until_completion(tmp_path):
    transport = FakeTransport(["?", "?p"])
    stage = WaynelabsStage(config(tmp_path), transport=transport, dry_run=False)

    actions = stage.trigger(mode="closed_loop")

    assert actions == ["?X11111p"]
    assert transport.reads >= 2


def test_closed_loop_trigger_accepts_coalesced_prompt_and_completion(tmp_path):
    transport = FakeTransport(["??p"])
    stage = WaynelabsStage(config(tmp_path), transport=transport, dry_run=False)

    actions = stage.trigger(mode="closed_loop")

    assert actions == ["?X11111p"]
    assert transport.reads >= 1


@pytest.mark.parametrize("response", ["?c!", "?c?b", "??pX"])
def test_completion_buffer_rejects_trailing_garbage_or_extra_marker(tmp_path, response):
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 10.0})
    stage = WaynelabsStage(config(tmp_path), transport=FakeTransport([response]), dry_run=False, ledger=ledger)

    with pytest.raises(DeviceError, match="unexpected"):
        stage.move_relative(axis="x", um=10, speed=8)

    assert ledger.states["x"] is AxisState.UNKNOWN


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
        self.reads = 0

    def write(self, data: bytes):
        self.writes.append(data)

    def readline(self):
        self.reads += 1
        if not self.responses:
            return b""
        return self.responses.pop(0).encode("ascii")

    def close(self):
        pass


class ReadErrorTransport:
    def __init__(self):
        self.writes = []

    def write(self, data: bytes):
        self.writes.append(data)

    def readline(self):
        raise OSError("serial read failed")

    def close(self):
        pass
