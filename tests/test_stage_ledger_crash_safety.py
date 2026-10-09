"""Crash-safety of the WayneLabs position ledger: atomic writes, two-phase
in-flight markers, and the configured safe home-direction guard."""

import json

import pytest

from lab_auto.config import StageConfig, load_devices_config
from lab_auto.devices.waynelabs_stage import AxisState, PositionLedger, WaynelabsStage
from lab_auto.errors import ConfigError, SafetyError


_DEFAULT_HOME = {"x": "negative", "y": "negative", "z": "positive"}


def make_config(tmp_path, *, home_direction=_DEFAULT_HOME):
    return StageConfig(
        type="waynelabs_linear",
        port="COM5",
        baudrate=9600,
        resolution_um={"x": 0.04, "y": 0.04, "z": 0.04},
        default_speed=8,
        soft_limits_um={"x": [-5000, 5000], "y": [-5000, 5000], "z": [-1000, 1000]},
        state_file=tmp_path / "stage_position.json",
        max_unknown_move_um=100,
        home_direction=home_direction,
    )


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.writes = []
        self.reads = 0

    def reset_input_buffer(self):
        pass

    def write(self, data: bytes):
        self.writes.append(data)

    def readline(self):
        self.reads += 1
        return self.responses.pop(0).encode("ascii") if self.responses else b""

    def close(self):
        pass


# --- atomic save -------------------------------------------------------

def test_ledger_save_is_atomic_and_leaves_no_tmp_residue(tmp_path):
    cfg = make_config(tmp_path)
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 12.0})

    ledger.save(cfg)

    assert cfg.state_file.exists()
    tmp = cfg.state_file.with_name(cfg.state_file.name + ".tmp")
    assert not tmp.exists()
    data = json.loads(cfg.state_file.read_text(encoding="utf-8"))
    assert data["states"]["x"] == "homed"
    assert data["in_flight"] == {}


# --- two-phase in-flight marker ---------------------------------------

def test_move_persists_in_flight_marker_before_sending_command(tmp_path):
    cfg = make_config(tmp_path)
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 100.0})

    class SpyTransport(FakeTransport):
        def __init__(self, config, responses):
            super().__init__(responses)
            self.config = config
            self.in_flight_at_write = None

        def write(self, data):
            # Snapshot the persisted ledger at the exact moment the motor command
            # is sent: the in-flight marker must already be on disk.
            self.in_flight_at_write = dict(PositionLedger.load(self.config).in_flight)
            super().write(data)

    transport = SpyTransport(cfg, ["?c"])
    stage = WaynelabsStage(cfg, transport=transport, dry_run=False, ledger=ledger)

    stage.move_relative(axis="x", um=10, speed=8)

    assert "x" in transport.in_flight_at_write


def test_load_forces_in_flight_axis_to_unknown(tmp_path):
    cfg = make_config(tmp_path)
    # A ledger persisted mid-move: state still HOMED but an in-flight marker present.
    PositionLedger(
        states={"x": AxisState.HOMED, "y": AxisState.USER_ZEROED, "z": AxisState.UNKNOWN},
        position_um={"x": 100.0, "y": 5.0, "z": 0.0},
        in_flight={"x": {"commanded_um": 40.0}},
    ).save(cfg)

    loaded = PositionLedger.load(cfg)

    assert loaded.states["x"] is AxisState.UNKNOWN  # crash mid-move -> must re-home
    assert loaded.states["y"] is AxisState.USER_ZEROED  # untouched axis stays trusted


def test_completed_move_clears_in_flight_marker(tmp_path):
    cfg = make_config(tmp_path)
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 100.0})
    stage = WaynelabsStage(cfg, transport=FakeTransport(["?c"]), dry_run=False, ledger=ledger)

    stage.move_relative(axis="x", um=10, speed=8)

    loaded = PositionLedger.load(cfg)
    assert loaded.in_flight == {}
    assert loaded.states["x"] is AxisState.HOMED
    assert loaded.position_um["x"] == 110.0


def test_error_path_clears_in_flight_marker(tmp_path):
    cfg = make_config(tmp_path)
    ledger = PositionLedger(states={"x": AxisState.HOMED}, position_um={"x": 10.0})
    # "?t" on a move is a limit hit -> axis marked unknown; the marker must clear too.
    stage = WaynelabsStage(cfg, transport=FakeTransport(["?t"]), dry_run=False, ledger=ledger)

    with pytest.raises(Exception):
        stage.move_relative(axis="x", um=10, speed=8)

    loaded = PositionLedger.load(cfg)
    assert loaded.states["x"] is AxisState.UNKNOWN
    assert loaded.in_flight == {}


def test_home_persists_and_clears_in_flight(tmp_path):
    cfg = make_config(tmp_path)
    stage = WaynelabsStage(cfg, transport=FakeTransport(["?t"]), dry_run=False, ledger=PositionLedger())

    stage.home(axis="x", direction="negative", speed=8)

    loaded = PositionLedger.load(cfg)
    assert loaded.states["x"] is AxisState.HOMED
    assert loaded.in_flight == {}


# --- backward compatibility -------------------------------------------

def test_load_accepts_old_ledger_without_in_flight_field(tmp_path):
    cfg = make_config(tmp_path)
    cfg.state_file.parent.mkdir(parents=True, exist_ok=True)
    cfg.state_file.write_text(
        json.dumps(
            {
                "states": {"x": "homed", "y": "unknown", "z": "unknown"},
                "position_um": {"x": 100.0, "y": 0.0, "z": 0.0},
                "resolution_um": {"x": 0.04, "y": 0.04, "z": 0.04},
                "device_identity": {"type": "waynelabs_linear", "port": "COM5"},
            }
        ),
        encoding="utf-8",
    )

    loaded = PositionLedger.load(cfg)

    assert loaded.states["x"] is AxisState.HOMED
    assert loaded.position_um["x"] == 100.0
    assert loaded.in_flight == {}


# --- home-direction config parsing ------------------------------------

def _devices_yaml(*, home_direction_line=""):
    return f"""
runtime: {{mode: dry_run, log_level: info}}
stage:
  type: waynelabs_linear
  port: COM5
  baudrate: 9600
  resolution_um: {{x: 0.04, y: 0.04, z: 0.04}}
  default_speed: 8
  soft_limits_um: {{x: [-5000, 5000], y: [-5000, 5000], z: [-1000, 1000]}}
  state_file: state/stage_position.json
  max_unknown_move_um: 100
{home_direction_line}
spectrometer: {{type: zolix, dll_path: C:/x.dll}}
camera: {{type: dfield_vs_a4, dll_path: C:/y.dll}}
light: {{type: manual, manual_light_control: true}}
"""


def test_config_parses_home_direction(tmp_path):
    path = tmp_path / "devices.yaml"
    path.write_text(
        _devices_yaml(home_direction_line="  home_direction: {x: positive, y: negative, z: positive}"),
        encoding="utf-8",
    )

    config = load_devices_config(path)

    assert config.stage.home_direction == {"x": "positive", "y": "negative", "z": "positive"}


def test_config_home_direction_optional_defaults_none(tmp_path):
    path = tmp_path / "devices.yaml"
    path.write_text(_devices_yaml(), encoding="utf-8")

    config = load_devices_config(path)

    assert config.stage.home_direction is None


def test_config_rejects_invalid_home_direction(tmp_path):
    path = tmp_path / "devices.yaml"
    path.write_text(_devices_yaml(home_direction_line="  home_direction: sideways"), encoding="utf-8")

    with pytest.raises(ConfigError, match="home_direction"):
        load_devices_config(path)


# --- home-direction runtime guard -------------------------------------

def test_real_home_requires_configured_direction(tmp_path):
    cfg = make_config(tmp_path, home_direction=None)
    transport = FakeTransport(["?t"])
    stage = WaynelabsStage(cfg, transport=transport, dry_run=False, ledger=PositionLedger())

    with pytest.raises(SafetyError, match="no configured safe home direction"):
        stage.home(axis="x", direction="negative", speed=8)

    assert transport.writes == []


def test_home_rejects_direction_that_disagrees_with_config(tmp_path):
    cfg = make_config(tmp_path, home_direction={"x": "negative", "y": "negative", "z": "positive"})
    transport = FakeTransport(["?t"])
    stage = WaynelabsStage(cfg, transport=transport, dry_run=False, ledger=PositionLedger())

    with pytest.raises(SafetyError, match="home direction"):
        stage.home(axis="x", direction="positive", speed=8)

    assert transport.writes == []  # refused before any command / ledger write
    assert not cfg.state_file.exists()


def test_home_allows_matching_configured_direction(tmp_path):
    cfg = make_config(tmp_path, home_direction={"x": "negative", "y": "negative", "z": "positive"})
    stage = WaynelabsStage(cfg, transport=FakeTransport(["?t"]), dry_run=False, ledger=PositionLedger())

    stage.home(axis="x", direction="negative", speed=8)

    assert stage.ledger.states["x"] is AxisState.HOMED
