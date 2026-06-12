# Phase 2 M2 Mapping Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Mapping area-scan workflow and `ramanctl mapping run` CLI that can plan, dry-run, simulate, and real-run an X/Y grid by reusing the existing stage safety ledger, light safety state machine, and single-point Raman/PL workflow.

**Architecture:** Keep Mapping above the existing hardware adapters: `WaynelabsStage` owns motion and the position ledger; `RamanWorkflow` owns one point acquisition; a new `MappingWorkflow` coordinates grid points, per-point output directories, manifest updates, and resume. Mapping must not write raw hardware protocol strings or bypass light/stage safety.

**Tech Stack:** Python 3.11+, standard library (`dataclasses`, `json`, `pathlib`, `datetime`), existing `PyYAML`, existing `pytest`, existing device/workflow adapters. No new third-party packages.

---

## Source Requirements

- Spec: `docs/superpowers/specs/2026-06-04-lab-automation-platform-design.md`
  - §12.1 stage coordinate state machine: Mapping requires X/Y `homed` or `user_zeroed`.
  - §12.2 light state machine: sample acquisition still requires `laser_state=on_confirmed`.
  - §12.3 safety constraints: real hardware must be explicit, dry-run first, errors close/confirm laser.
  - §15 Phase 2 scope: Mapping grid scan.
  - §17 Agent constraints: workflows must be interruptible, resumable, and auditable.
- Scope plan: `docs/superpowers/plans/2026-06-09-lab-automation-phase2-scope.md` §4 M2.
- Repository rules: `AGENTS.md`.

## Scope

In scope:
- `stage set-zero` real-mode CLI and adapter method for explicitly marking an axis `user_zeroed`; non-real `set-zero` may validate and print a planned action, but must not persist the safety ledger.
- Mapping config loader and example config.
- Pure X/Y grid generation with inclusive endpoints.
- Mapping manifest with point status, coordinates, run directory, timestamps, and errors.
- Resume by skipping manifest points already marked `complete`.
- Dry-run output that lists stage moves and per-point single-point actions without touching hardware.
- Simulated and real execution paths that reuse existing `RamanWorkflow` and close devices through `finally`.
- Hardware acceptance checklist for Mapping, deferred like Phase 1 and M1.

Out of scope:
- Sample recognition / automatic sample localization.
- Peak detection, baseline correction, auto exposure, batch scheduling beyond one Mapping grid.
- Daemon/session mode and Agent tool schema.
- Serpentine scan order. M2 uses deterministic row-major order to reduce implementation surface.

## File Map

```text
src/lab_auto/devices/waynelabs_stage.py        # add set_zero() and assert_mapping_ready()
src/lab_auto/cli.py                            # add stage set-zero and mapping run commands
src/lab_auto/config.py                         # add MappingConfig dataclasses and load_mapping_config()
src/lab_auto/devices/factory.py                # add create_mapping_workflow() real wiring
src/lab_auto/workflow/mapping.py               # create grid, manifest, MappingWorkflow
configs/mapping.example.yaml                   # create example mapping config
docs/phase2-mapping-hardware-acceptance.md     # create deferred real-hardware checklist
tests/test_stage_safety.py                     # add set-zero / mapping-ready coverage
tests/test_mapping_config.py                   # create config parser tests
tests/test_mapping_workflow.py                 # create grid/manifest/workflow tests
tests/test_hardware_cli.py                     # add stage set-zero real CLI safety test
tests/test_cli.py                              # add mapping CLI dry-run/simulated tests
tests/test_real_workflow_cli.py                # add real mapping factory/close path test
```

## Execution Rules

- Every code task starts with a failing test step, then run-to-red, then implementation, then run-to-green.
- Mapping real mode must require both `--real` and `--yes`.
- Mapping must require X/Y stage states to be `homed` or `user_zeroed` before planning any point.
- Mapping must move by relative deltas from the ledger position; it must not assume absolute stage readback.
- Mapping grid coordinates and steps must align to the configured stage resolution so requested coordinates match commanded hardware positions.
- Mapping must validate every grid target against X/Y soft limits before moving, so dry-run/simulated cannot pass a grid that real mode will reject partway through.
- Real Mapping must validate the referenced single-point workflow config before opening or moving hardware.
- Each point must get a stable `point_id` and its own output directory.
- Manifest writes are atomic enough for local CLI use: write to `manifest.json.tmp`, then replace `manifest.json`.
- On point failure, write the error into the manifest, best-effort close/confirm laser through `RamanWorkflow`, then stop with a non-zero CLI exit.
- Do not add protocol strings outside `src/lab_auto/devices/raw/*`.

---

## Task 1: Stage Set-Zero and Mapping Readiness

**Files:**
- Modify: `src/lab_auto/devices/waynelabs_stage.py`
- Modify: `src/lab_auto/cli.py`
- Modify: `tests/test_stage_safety.py`
- Modify: `tests/test_hardware_cli.py`

- [ ] **Step 1: Write stage ledger tests**

Add to `tests/test_stage_safety.py`:

```python
from lab_auto.devices.waynelabs_stage import AxisState, PositionLedger, WaynelabsStage
from lab_auto.errors import SafetyError


def test_set_zero_marks_axis_user_zeroed(tmp_path):
    ledger = PositionLedger()
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True, ledger=ledger)

    stage.set_zero(axis="x")

    assert ledger.states["x"] is AxisState.USER_ZEROED
    assert ledger.position_um["x"] == 0.0


def test_assert_mapping_ready_requires_x_and_y_known(tmp_path):
    ledger = PositionLedger()
    ledger.states["x"] = AxisState.USER_ZEROED
    ledger.states["y"] = AxisState.UNKNOWN
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True, ledger=ledger)

    with pytest.raises(SafetyError, match="Mapping requires X/Y"):
        stage.assert_mapping_ready()


def test_assert_mapping_ready_accepts_homed_or_user_zeroed_xy(tmp_path):
    ledger = PositionLedger()
    ledger.states["x"] = AxisState.HOMED
    ledger.states["y"] = AxisState.USER_ZEROED
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True, ledger=ledger)

    stage.assert_mapping_ready()
```

- [ ] **Step 2: Run tests to verify missing methods fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_stage_safety.py -q
```

Expected: fail with `AttributeError` for `set_zero` and `assert_mapping_ready`.

- [ ] **Step 3: Implement stage methods**

Add to `WaynelabsStage`:

```python
    def set_zero(self, *, axis: str) -> None:
        self._assert_linear_controller()
        self._assert_axis_supported(axis)
        self.ledger.states[axis] = AxisState.USER_ZEROED
        self.ledger.position_um[axis] = 0.0
        self._save_ledger()

    def assert_mapping_ready(self) -> None:
        for axis in ("x", "y"):
            self._assert_axis_supported(axis)
            state = self.ledger.states.get(axis, AxisState.UNKNOWN)
            if state not in (AxisState.HOMED, AxisState.USER_ZEROED):
                raise SafetyError("Mapping requires X/Y axes to be homed or user_zeroed")
            if axis not in self.ledger.position_um or not math.isfinite(self.ledger.position_um[axis]):
                raise SafetyError(f"Mapping requires a finite known position for axis {axis}")
```

- [ ] **Step 4: Write CLI tests for `stage set-zero`**

Add to `tests/test_hardware_cli.py`:

```python
def test_stage_set_zero_dry_run_does_not_persist_ledger(tmp_path: Path, capsys):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)
    state_file = tmp_path / "stage.json"
    text = devices.read_text(encoding="utf-8").replace("state/stage_position.json", str(state_file))
    devices.write_text(text, encoding="utf-8")

    exit_code = main(["stage", "set-zero", "--config", str(devices), "--dry-run", "--axis", "x", "--yes"])

    assert exit_code == 0
    assert "stage_set_zero:x" in capsys.readouterr().out
    assert not state_file.exists()


def test_stage_set_zero_real_requires_yes(tmp_path: Path, capsys):
    devices = tmp_path / "devices.real.yaml"
    write_devices_config(devices)

    exit_code = main(["stage", "set-zero", "--config", str(devices), "--axis", "x", "--real"])

    assert exit_code == 2
    assert "requires --yes" in capsys.readouterr().out
```

- [ ] **Step 5: Implement CLI parser and handling**

In `build_parser()`, add under `stage_sub`:

```python
    set_zero = stage_sub.add_parser("set-zero")
    set_zero.add_argument("--config", required=True)
    set_zero.add_argument("--axis", required=True)
    set_zero.add_argument("--yes", action="store_true")
    add_runtime_flags(set_zero)
```

In `_validate_real_hardware_args()` stage branch:

```python
        elif args.command == "set-zero":
            if not args.yes:
                raise ConfigError("real stage set-zero requires --yes")
            stage._assert_axis_supported(args.axis)
```

In `_run_non_real_hardware_command()` stage branch:

```python
        if args.command == "set-zero":
            if not args.yes:
                raise ConfigError("stage set-zero requires --yes")
            stage._assert_axis_supported(args.axis)
            return _print_dry_run(f"stage_set_zero:{args.axis}")
```

In `_run_real_hardware_command()` stage branch:

```python
    if args.domain == "stage" and args.command == "set-zero":
        if not args.yes:
            raise ConfigError("real stage set-zero requires --yes")
        stage = factory.create_stage(devices_config)
        try:
            stage.set_zero(axis=args.axis)
        finally:
            stage.close()
        print(f"stage_set_zero:{args.axis}")
        return 0
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_stage_safety.py tests/test_hardware_cli.py -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/lab_auto/devices/waynelabs_stage.py src/lab_auto/cli.py tests/test_stage_safety.py tests/test_hardware_cli.py
git commit -m "feat(stage): add user zero for mapping readiness"
```

---

## Task 2: Mapping Configuration

**Files:**
- Modify: `src/lab_auto/config.py`
- Create: `configs/mapping.example.yaml`
- Create: `tests/test_mapping_config.py`

- [ ] **Step 1: Write mapping config tests**

Create `tests/test_mapping_config.py`:

```python
from pathlib import Path

import pytest

from lab_auto.config import load_mapping_config
from lab_auto.errors import ConfigError


def write_mapping(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


VALID_MAPPING = """
devices_config: configs/devices.example.yaml
single_point_config: configs/single_point.example.yaml
mapping:
  x: {start_um: 0, end_um: 100, step_um: 50}
  y: {start_um: 0, end_um: 50, step_um: 50}
  speed: 8
  resume: true
output:
  directory: output/mapping
"""


def test_mapping_config_loads(tmp_path: Path):
    cfg = load_mapping_config(write_mapping(tmp_path / "mapping.yaml", VALID_MAPPING))

    assert cfg.devices_config == Path("configs/devices.example.yaml")
    assert cfg.single_point_config == Path("configs/single_point.example.yaml")
    assert cfg.x.start_um == 0.0
    assert cfg.x.end_um == 100.0
    assert cfg.x.step_um == 50.0
    assert cfg.y.end_um == 50.0
    assert cfg.speed == 8
    assert cfg.resume is True
    assert cfg.output_directory == Path("output/mapping")


@pytest.mark.parametrize(
    "bad_text, message",
    [
        (VALID_MAPPING.replace("step_um: 50", "step_um: 0", 1), "step_um"),
        (VALID_MAPPING.replace("end_um: 100", "end_um: -100", 1), "direction"),
        (VALID_MAPPING.replace("speed: 8", "speed: 0"), "speed"),
        (VALID_MAPPING.replace("resume: true", "resume: maybe"), "resume"),
    ],
)
def test_mapping_config_rejects_invalid_values(tmp_path: Path, bad_text: str, message: str):
    with pytest.raises(ConfigError, match=message):
        load_mapping_config(write_mapping(tmp_path / "mapping.yaml", bad_text))
```

- [ ] **Step 2: Run tests to verify parser is missing**

Run:

```bash
.venv/bin/python -m pytest tests/test_mapping_config.py -q
```

Expected: import failure for `load_mapping_config`.

- [ ] **Step 3: Implement config dataclasses and loader**

Add to `src/lab_auto/config.py`:

```python
@dataclass(frozen=True)
class MappingAxisConfig:
    start_um: float
    end_um: float
    step_um: float


@dataclass(frozen=True)
class MappingConfig:
    devices_config: Path
    single_point_config: Path
    x: MappingAxisConfig
    y: MappingAxisConfig
    speed: int
    resume: bool
    output_directory: Path
```

Add helpers:

```python
def _mapping_axis(name: str, value: Any) -> MappingAxisConfig:
    if not isinstance(value, dict):
        raise ConfigError(f"mapping.{name} must be a mapping")
    axis = MappingAxisConfig(
        start_um=_finite_float(value["start_um"], field=f"mapping.{name}.start_um"),
        end_um=_finite_float(value["end_um"], field=f"mapping.{name}.end_um"),
        step_um=_finite_float(value["step_um"], field=f"mapping.{name}.step_um"),
    )
    if axis.step_um == 0:
        raise ConfigError(f"mapping.{name}.step_um must be non-zero")
    if (axis.end_um - axis.start_um) * axis.step_um < 0:
        raise ConfigError(f"mapping.{name}.step_um direction must move from start_um to end_um")
    return axis
```

Add loader:

```python
def load_mapping_config(path: str | Path) -> MappingConfig:
    config_path = Path(path)
    data = _read_yaml(config_path)
    try:
        mapping = data["mapping"]
        output = data["output"]
        speed = _finite_int(mapping["speed"], field="mapping.speed")
        if speed <= 0:
            raise ConfigError("mapping.speed must be positive")
        return MappingConfig(
            devices_config=Path(data["devices_config"]),
            single_point_config=Path(data["single_point_config"]),
            x=_mapping_axis("x", mapping["x"]),
            y=_mapping_axis("y", mapping["y"]),
            speed=speed,
            resume=_as_bool(mapping.get("resume", True), field="mapping.resume"),
            output_directory=Path(output["directory"]),
        )
    except KeyError as exc:
        raise ConfigError(f"missing required mapping configuration field: {exc.args[0]} in {config_path}") from exc
```

- [ ] **Step 4: Add example config**

Create `configs/mapping.example.yaml`:

```yaml
devices_config: configs/devices.example.yaml
single_point_config: configs/single_point.example.yaml

mapping:
  x: {start_um: 0, end_um: 100, step_um: 50}
  y: {start_um: 0, end_um: 50, step_um: 50}
  speed: 8
  resume: true

output:
  directory: output/mapping
```

- [ ] **Step 5: Run mapping config tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_mapping_config.py tests/test_config.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/lab_auto/config.py configs/mapping.example.yaml tests/test_mapping_config.py
git commit -m "feat(mapping): add mapping configuration"
```

---

## Task 3: Grid Planner and Manifest

**Files:**
- Create: `src/lab_auto/workflow/mapping.py`
- Create: `tests/test_mapping_workflow.py`

- [ ] **Step 1: Write pure grid and manifest tests**

Create `tests/test_mapping_workflow.py`:

```python
import json
from pathlib import Path

from lab_auto.config import MappingAxisConfig, MappingConfig
from lab_auto.workflow.mapping import build_grid, load_manifest, mark_point_complete, mark_point_failed, point_output_dir


def mapping_config(tmp_path: Path) -> MappingConfig:
    return MappingConfig(
        devices_config=Path("configs/devices.example.yaml"),
        single_point_config=Path("configs/single_point.example.yaml"),
        x=MappingAxisConfig(start_um=0, end_um=100, step_um=50),
        y=MappingAxisConfig(start_um=0, end_um=50, step_um=50),
        speed=8,
        resume=True,
        output_directory=tmp_path,
    )


def test_build_grid_uses_inclusive_row_major_points(tmp_path: Path):
    points = build_grid(mapping_config(tmp_path))

    assert [(p.point_id, p.x_um, p.y_um) for p in points] == [
        ("r000_c000", 0.0, 0.0),
        ("r000_c001", 50.0, 0.0),
        ("r000_c002", 100.0, 0.0),
        ("r001_c000", 0.0, 50.0),
        ("r001_c001", 50.0, 50.0),
        ("r001_c002", 100.0, 50.0),
    ]


def test_point_output_dir_is_stable(tmp_path: Path):
    point = build_grid(mapping_config(tmp_path))[4]

    assert point_output_dir(mapping_config(tmp_path), point) == tmp_path / "r001_c001"


def test_manifest_complete_points_can_be_loaded(tmp_path: Path):
    cfg = mapping_config(tmp_path)
    point = build_grid(cfg)[0]

    mark_point_complete(cfg, point, run_dir=tmp_path / point.point_id)

    manifest = load_manifest(cfg)
    assert manifest["points"][point.point_id]["status"] == "complete"
    assert manifest["points"][point.point_id]["x_um"] == 0.0


def test_manifest_failed_points_record_error(tmp_path: Path):
    cfg = mapping_config(tmp_path)
    point = build_grid(cfg)[0]

    mark_point_failed(cfg, point, error="sample capture failed")

    manifest = load_manifest(cfg)
    assert manifest["points"][point.point_id]["status"] == "failed"
    assert manifest["points"][point.point_id]["error"] == "sample capture failed"
```

- [ ] **Step 2: Run tests to verify module is missing**

Run:

```bash
.venv/bin/python -m pytest tests/test_mapping_workflow.py -q
```

Expected: import failure for `lab_auto.workflow.mapping`.

- [ ] **Step 3: Implement planner and manifest helpers**

Create `src/lab_auto/workflow/mapping.py` with:

```python
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from lab_auto.config import MappingAxisConfig, MappingConfig


@dataclass(frozen=True)
class MappingPoint:
    point_id: str
    row: int
    col: int
    x_um: float
    y_um: float


def _axis_values(axis: MappingAxisConfig) -> list[float]:
    values: list[float] = []
    current = axis.start_um
    if axis.step_um > 0:
        while current <= axis.end_um + 1e-9:
            values.append(round(current, 9))
            current += axis.step_um
    else:
        while current >= axis.end_um - 1e-9:
            values.append(round(current, 9))
            current += axis.step_um
    return values


def build_grid(config: MappingConfig) -> list[MappingPoint]:
    points: list[MappingPoint] = []
    for row, y_um in enumerate(_axis_values(config.y)):
        for col, x_um in enumerate(_axis_values(config.x)):
            points.append(MappingPoint(point_id=f"r{row:03d}_c{col:03d}", row=row, col=col, x_um=x_um, y_um=y_um))
    return points


def manifest_path(config: MappingConfig) -> Path:
    return config.output_directory / "manifest.json"


def point_output_dir(config: MappingConfig, point: MappingPoint) -> Path:
    return config.output_directory / point.point_id


def load_manifest(config: MappingConfig) -> dict:
    path = manifest_path(config)
    if not path.exists():
        return {"points": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(config: MappingConfig, manifest: dict) -> None:
    config.output_directory.mkdir(parents=True, exist_ok=True)
    path = manifest_path(config)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def mark_point_complete(config: MappingConfig, point: MappingPoint, *, run_dir: Path) -> None:
    manifest = load_manifest(config)
    manifest.setdefault("points", {})[point.point_id] = {
        "status": "complete",
        "x_um": point.x_um,
        "y_um": point.y_um,
        "run_dir": str(run_dir),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    save_manifest(config, manifest)


def mark_point_failed(config: MappingConfig, point: MappingPoint, *, error: str) -> None:
    manifest = load_manifest(config)
    manifest.setdefault("points", {})[point.point_id] = {
        "status": "failed",
        "x_um": point.x_um,
        "y_um": point.y_um,
        "error": error,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    }
    save_manifest(config, manifest)
```

- [ ] **Step 4: Run planner tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_mapping_workflow.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/lab_auto/workflow/mapping.py tests/test_mapping_workflow.py
git commit -m "feat(mapping): add grid planner and manifest"
```

---

## Task 4: Mapping Workflow Dry-Run, Simulated Run, and Resume

**Files:**
- Modify: `src/lab_auto/workflow/mapping.py`
- Modify: `tests/test_mapping_workflow.py`

- [ ] **Step 1: Write workflow coordination tests**

Add to `tests/test_mapping_workflow.py`:

```python
import pytest

from lab_auto.errors import ConfigError, SafetyError
from lab_auto.devices.waynelabs_stage import AxisState, PositionLedger
from lab_auto.workflow.mapping import MappingWorkflow, load_manifest


class FakeStage:
    def __init__(self):
        self.config = type(
            "FakeStageConfig",
            (),
            {
                "resolution_um": {"x": 50.0, "y": 50.0},
                "soft_limits_um": {"x": [-5000.0, 5000.0], "y": [-5000.0, 5000.0]},
            },
        )()
        self.ledger = PositionLedger()
        self.ledger.states["x"] = AxisState.USER_ZEROED
        self.ledger.states["y"] = AxisState.USER_ZEROED
        self.ledger.position_um["x"] = 0.0
        self.ledger.position_um["y"] = 0.0
        self.moves = []

    def assert_mapping_ready(self):
        for axis in ("x", "y"):
            if self.ledger.states[axis] is AxisState.UNKNOWN:
                raise SafetyError("Mapping requires X/Y axes to be homed or user_zeroed")

    def move_relative(self, *, axis: str, um: float, speed: int):
        self.moves.append((axis, um, speed))
        self.ledger.position_um[axis] += um


class FailingStage(FakeStage):
    def move_relative(self, *, axis: str, um: float, speed: int):
        if um != 0:
            raise SafetyError("soft limit")
        super().move_relative(axis=axis, um=um, speed=speed)


class FakePointRunner:
    def __init__(self):
        self.run_dirs = []

    def measure_single_point(self, point, output_dir):
        self.run_dirs.append(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def plan_single_point(self):
        return ["confirm_laser_off", "capture_background", "confirm_laser_on", "capture_sample", "save_outputs"]


def test_mapping_dry_run_lists_moves_and_single_point_actions(tmp_path: Path):
    cfg = mapping_config(tmp_path)
    workflow = MappingWorkflow(config=cfg, stage=FakeStage(), point_runner=FakePointRunner(), dry_run=True)

    actions = workflow.plan_actions()

    assert actions[0] == "mapping_point:r000_c000:x=0.0:y=0.0"
    assert "stage_move:x:50.0" in actions
    assert "confirm_laser_on" in actions


def test_mapping_run_skips_completed_points_when_resume_enabled(tmp_path: Path):
    cfg = mapping_config(tmp_path)
    first = build_grid(cfg)[0]
    mark_point_complete(cfg, first, run_dir=tmp_path / first.point_id)
    runner = FakePointRunner()

    MappingWorkflow(config=cfg, stage=FakeStage(), point_runner=runner, dry_run=False).run()

    assert len(runner.run_dirs) == len(build_grid(cfg)) - 1


class FailingPointRunner(FakePointRunner):
    def measure_single_point(self, point, output_dir):
        raise RuntimeError("sample capture failed")


def test_mapping_run_records_failed_point_before_reraising(tmp_path: Path):
    cfg = mapping_config(tmp_path)

    with pytest.raises(RuntimeError, match="sample capture failed"):
        MappingWorkflow(config=cfg, stage=FakeStage(), point_runner=FailingPointRunner(), dry_run=False).run()

    first = build_grid(cfg)[0]
    manifest = load_manifest(cfg)
    assert manifest["points"][first.point_id]["status"] == "failed"
    assert manifest["points"][first.point_id]["error"] == "sample capture failed"


def test_mapping_run_records_failed_stage_move_before_reraising(tmp_path: Path):
    cfg = mapping_config(tmp_path)
    first = build_grid(cfg)[0]
    mark_point_complete(cfg, first, run_dir=tmp_path / first.point_id)

    with pytest.raises(SafetyError, match="soft limit"):
        MappingWorkflow(config=cfg, stage=FailingStage(), point_runner=FakePointRunner(), dry_run=False).run()

    second = build_grid(cfg)[1]
    manifest = load_manifest(cfg)
    assert manifest["points"][second.point_id]["status"] == "failed"
    assert manifest["points"][second.point_id]["error"] == "soft limit"


def test_mapping_rejects_grid_not_aligned_to_stage_resolution(tmp_path: Path):
    cfg = MappingConfig(
        devices_config=Path("configs/devices.example.yaml"),
        single_point_config=Path("configs/single_point.example.yaml"),
        x=MappingAxisConfig(start_um=0, end_um=75, step_um=25),
        y=MappingAxisConfig(start_um=0, end_um=0, step_um=50),
        speed=8,
        resume=True,
        output_directory=tmp_path,
    )

    with pytest.raises(ConfigError, match="resolution"):
        MappingWorkflow(config=cfg, stage=FakeStage(), point_runner=FakePointRunner(), dry_run=True)


def test_mapping_rejects_grid_target_outside_soft_limits(tmp_path: Path):
    cfg = MappingConfig(
        devices_config=Path("configs/devices.example.yaml"),
        single_point_config=Path("configs/single_point.example.yaml"),
        x=MappingAxisConfig(start_um=0, end_um=5500, step_um=50),
        y=MappingAxisConfig(start_um=0, end_um=0, step_um=50),
        speed=8,
        resume=True,
        output_directory=tmp_path,
    )

    with pytest.raises(SafetyError, match="soft limit"):
        MappingWorkflow(config=cfg, stage=FakeStage(), point_runner=FakePointRunner(), dry_run=True)
```

- [ ] **Step 2: Run workflow tests to verify missing class fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_mapping_workflow.py -q
```

Expected: import failure for `MappingWorkflow`.

- [ ] **Step 3: Implement `MappingWorkflow`**

Add to `src/lab_auto/workflow/mapping.py`:

```python
from lab_auto.errors import ConfigError, SafetyError


class MappingWorkflow:
    def __init__(self, *, config: MappingConfig, stage, point_runner, dry_run: bool):
        self.config = config
        self.stage = stage
        self.point_runner = point_runner
        self.dry_run = dry_run
        assert_grid_aligned_to_stage_resolution(config, stage)
        assert_grid_targets_within_soft_limits(config, stage)
        self.position_um = {
            "x": float(stage.ledger.position_um["x"]),
            "y": float(stage.ledger.position_um["y"]),
        }

    def _completed_points(self) -> set[str]:
        if not self.config.resume:
            return set()
        manifest = load_manifest(self.config)
        return {
            point_id
            for point_id, entry in manifest.get("points", {}).items()
            if entry.get("status") == "complete"
        }

    def _move_to(self, point: MappingPoint) -> list[str]:
        moves: list[str] = []
        dx = point.x_um - self.position_um["x"]
        dy = point.y_um - self.position_um["y"]
        if dy != 0:
            self.stage.move_relative(axis="y", um=dy, speed=self.config.speed)
            moves.append(f"stage_move:y:{dy}")
            self.position_um["y"] = point.y_um
        if dx != 0:
            self.stage.move_relative(axis="x", um=dx, speed=self.config.speed)
            moves.append(f"stage_move:x:{dx}")
            self.position_um["x"] = point.x_um
        return moves

    def plan_actions(self) -> list[str]:
        self.stage.assert_mapping_ready()
        actions: list[str] = []
        completed = self._completed_points()
        for point in build_grid(self.config):
            if point.point_id in completed:
                actions.append(f"mapping_skip:{point.point_id}")
                continue
            actions.append(f"mapping_point:{point.point_id}:x={point.x_um}:y={point.y_um}")
            actions.extend(self._move_to(point))
            actions.extend(self.point_runner.plan_single_point())
        return actions

    def run(self) -> Path:
        self.stage.assert_mapping_ready()
        completed = self._completed_points()
        for point in build_grid(self.config):
            if point.point_id in completed:
                continue
            try:
                self._move_to(point)
                run_dir = self.point_runner.measure_single_point(point, point_output_dir(self.config, point))
            except Exception as exc:
                mark_point_failed(self.config, point, error=str(exc))
                raise
            else:
                mark_point_complete(self.config, point, run_dir=run_dir)
        return manifest_path(self.config)


def _is_aligned(value: float, resolution: float) -> bool:
    quotient = value / resolution
    return abs(quotient - round(quotient)) <= 1e-9


def assert_grid_aligned_to_stage_resolution(config: MappingConfig, stage) -> None:
    try:
        resolution_um = stage.config.resolution_um
    except AttributeError as exc:
        raise ConfigError("Mapping stage must expose resolution_um") from exc
    for axis_name, axis_config in (("x", config.x), ("y", config.y)):
        resolution = float(resolution_um[axis_name])
        for field_name, value in (
            ("start_um", axis_config.start_um),
            ("end_um", axis_config.end_um),
            ("step_um", axis_config.step_um),
        ):
            if not _is_aligned(value, resolution):
                raise ConfigError(f"mapping.{axis_name}.{field_name} must align to stage resolution {resolution} um")


def assert_grid_targets_within_soft_limits(config: MappingConfig, stage) -> None:
    try:
        soft_limits_um = stage.config.soft_limits_um
    except AttributeError as exc:
        raise ConfigError("Mapping stage must expose soft_limits_um") from exc
    for point in build_grid(config):
        for axis_name, value in (("x", point.x_um), ("y", point.y_um)):
            low, high = soft_limits_um[axis_name]
            if value < low or value > high:
                raise SafetyError(f"mapping point {point.point_id} exceeds soft limit for axis {axis_name}")
```

- [ ] **Step 4: Run mapping workflow tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_mapping_workflow.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/lab_auto/workflow/mapping.py tests/test_mapping_workflow.py
git commit -m "feat(mapping): add mapping workflow coordination"
```

---

## Task 5: CLI and Factory Wiring

**Files:**
- Modify: `src/lab_auto/cli.py`
- Modify: `src/lab_auto/devices/factory.py`
- Modify: `src/lab_auto/workflow/mapping.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_real_workflow_cli.py`

- [ ] **Step 1: Add CLI tests**

Add to `tests/test_cli.py`:

```python
def test_mapping_run_dry_run_prints_plan(tmp_path: Path, capsys):
    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(
        f"""
devices_config: configs/devices.example.yaml
single_point_config: configs/single_point.example.yaml
mapping:
  x: {{start_um: 0, end_um: 50, step_um: 50}}
  y: {{start_um: 0, end_um: 0, step_um: 50}}
  speed: 8
  resume: false
output:
  directory: {tmp_path / "mapping-out"}
""",
        encoding="utf-8",
    )

    exit_code = main(["mapping", "run", "--config", str(mapping), "--dry-run", "--assume-user-zeroed"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "mapping_point:r000_c000:x=0.0:y=0.0" in out
    assert "mapping_point:r000_c001:x=50.0:y=0.0" in out
    assert "confirm_laser_on" in out
```

The `--assume-user-zeroed` flag is dry-run/simulated only. It initializes an in-memory X/Y `user_zeroed` ledger for planning demos without changing the real safety rule.

Add to `tests/test_real_workflow_cli.py`:

```python
def test_mapping_run_real_uses_factory_and_closes_workflow(tmp_path: Path, capsys):
    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(
        f"""
devices_config: configs/devices.example.yaml
single_point_config: configs/single_point.example.yaml
mapping:
  x: {{start_um: 0, end_um: 0, step_um: 50}}
  y: {{start_um: 0, end_um: 0, step_um: 50}}
  speed: 8
  resume: false
output:
  directory: {tmp_path / "mapping-out"}
""",
        encoding="utf-8",
    )
    factory = FakeMappingFactory(tmp_path / "mapping-out" / "manifest.json")

    exit_code = main(["mapping", "run", "--config", str(mapping), "--real", "--yes"], factory=factory)

    assert exit_code == 0
    assert factory.workflow.calls == [("run",), ("close",)]
    assert "manifest.json" in capsys.readouterr().out


def test_mapping_run_real_invalid_single_point_config_fails_before_factory(tmp_path: Path, capsys):
    single = tmp_path / "single_point.yaml"
    single.write_text(
        f"""
devices_config: configs/devices.example.yaml
sample: {{id: sample-001, operator: lab}}
optics: {{entrance_port: side, exit_port: direct, grating: 1, center_wavelength_nm: 600, slit_width_um: 100}}
acquisition: {{exposure_ms: 1000, gain: low, read_mode: image, frames: 1, subtract_background: true}}
output: {{directory: {tmp_path / "out"}, formats: [csv, json]}}
""",
        encoding="utf-8",
    )
    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(
        f"""
devices_config: configs/devices.example.yaml
single_point_config: {single}
mapping:
  x: {{start_um: 0, end_um: 0, step_um: 50}}
  y: {{start_um: 0, end_um: 0, step_um: 50}}
  speed: 8
  resume: false
output:
  directory: {tmp_path / "mapping-out"}
""",
        encoding="utf-8",
    )
    factory = FakeMappingFactory(tmp_path / "mapping-out" / "manifest.json")

    exit_code = main(["mapping", "run", "--config", str(mapping), "--real", "--yes"], factory=factory)

    assert exit_code == 2
    assert factory.created is False
    assert "read_mode=fvb" in capsys.readouterr().out


class FakeMappingFactory:
    def __init__(self, manifest_path: Path):
        self.workflow = FakeMappingWorkflow(manifest_path)
        self.created = False

    def create_mapping_workflow(self, mapping_config, *, require_confirmation: bool):
        self.created = True
        return self.workflow


class FakeMappingWorkflow:
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.calls = []

    def run(self):
        self.calls.append(("run",))
        return self.manifest_path

    def close(self):
        self.calls.append(("close",))
```

- [ ] **Step 2: Run CLI tests to verify command is missing**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_mapping_run_dry_run_prints_plan tests/test_real_workflow_cli.py::test_mapping_run_real_uses_factory_and_closes_workflow -q
```

Expected: parser failure for missing `mapping` command.

- [ ] **Step 3: Implement CLI parser**

In `build_parser()`:

```python
    mapping = subparsers.add_parser("mapping")
    mapping_sub = mapping.add_subparsers(dest="command", required=True)
    mapping_run = mapping_sub.add_parser("run")
    mapping_run.add_argument("--config", required=True)
    mapping_run.add_argument("--devices-config")
    mapping_run.add_argument("--yes", action="store_true")
    mapping_run.add_argument("--assume-user-zeroed", action="store_true")
    add_runtime_flags(mapping_run)
```

- [ ] **Step 4: Implement point runner helpers**

Add to `src/lab_auto/workflow/mapping.py`:

```python
from dataclasses import replace
from lab_auto.config import OutputConfig, WorkflowConfig
from lab_auto.workflow.raman import RamanWorkflow


class RamanPointRunner:
    def __init__(self, workflow: RamanWorkflow, *, require_confirmation: bool):
        self.workflow = workflow
        self.require_confirmation = require_confirmation

    def _with_output_dir(self, output_dir: Path) -> WorkflowConfig:
        return replace(self.workflow.config, output=OutputConfig(directory=output_dir, formats=self.workflow.config.output.formats))

    def plan_single_point(self) -> list[str]:
        return self.workflow.measure_single_point(require_confirmation=self.require_confirmation)

    def measure_single_point(self, point: MappingPoint, output_dir: Path) -> Path:
        original = self.workflow.config
        self.workflow.config = self._with_output_dir(output_dir)
        try:
            return self.workflow.run_single_point(require_confirmation=self.require_confirmation)
        finally:
            self.workflow.config = original
```

- [ ] **Step 5: Implement factory real wiring**

Add to `src/lab_auto/devices/factory.py`:

```python
    def create_mapping_workflow(self, mapping_config, *, require_confirmation: bool):
        from lab_auto.config import load_workflow_config, load_devices_config
        from lab_auto.workflow.mapping import MappingWorkflow, RamanPointRunner

        workflow_config = load_workflow_config(mapping_config.single_point_config)
        devices_config = load_devices_config(mapping_config.devices_config)
        RamanWorkflow.dry_run(workflow_config).validate_single_point_config()
        stage = None
        light = None
        spectrometer = None
        camera = None
        try:
            stage = self.create_stage(devices_config)
            stage.assert_mapping_ready()
            light = self.create_light(devices_config)
            spectrometer = self.create_spectrometer(devices_config)
            camera = self.create_camera(devices_config)
            raman = RamanWorkflow.real(workflow_config, stage=stage, spectrometer=spectrometer, camera=camera, light=light)
            return MappingWorkflow(
                config=mapping_config,
                stage=stage,
                point_runner=RamanPointRunner(raman, require_confirmation=require_confirmation),
                dry_run=False,
                closeables=[raman],
            )
        except Exception:
            for device in (camera, spectrometer, stage, light):
                if device is not None:
                    close = getattr(device, "close", None)
                    if close is not None:
                        close()
            raise
```

Extend `MappingWorkflow.__init__` and `close()`:

```python
    def __init__(self, *, config: MappingConfig, stage, point_runner, dry_run: bool, closeables: list[object] | None = None):
        self.config = config
        self.stage = stage
        self.point_runner = point_runner
        self.dry_run = dry_run
        assert_grid_aligned_to_stage_resolution(config, stage)
        assert_grid_targets_within_soft_limits(config, stage)
        self.position_um = {
            "x": float(stage.ledger.position_um["x"]),
            "y": float(stage.ledger.position_um["y"]),
        }
        self.closeables = closeables or []

    def close(self) -> None:
        for item in self.closeables:
            close = getattr(item, "close", None)
            if close is not None:
                close()
```

- [ ] **Step 6: Implement CLI handling**

In `main()` before the single workflow branch:

```python
        if args.domain == "mapping" and args.command == "run":
            from lab_auto.config import load_mapping_config, load_workflow_and_devices
            from lab_auto.workflow.mapping import MappingWorkflow, RamanPointRunner

            mapping_config = load_mapping_config(args.config)
            if args.devices_config is not None:
                mapping_config = replace(mapping_config, devices_config=Path(args.devices_config))
            workflow_config, devices_config = load_workflow_and_devices(mapping_config.single_point_config, devices_override=mapping_config.devices_config)
            RamanWorkflow.dry_run(workflow_config).validate_single_point_config()
            mode = resolve_runtime_mode(devices_config.runtime.mode, cli_real=args.real, cli_dry_run=args.dry_run, cli_simulated=args.simulated)
            devices_config = _with_runtime_mode(devices_config, mode)
            if mode is RuntimeMode.REAL:
                if args.assume_user_zeroed:
                    raise ConfigError("--assume-user-zeroed is only allowed for dry-run/simulated mapping")
                if not args.yes:
                    raise ConfigError("real mapping run requires --yes")
                workflow = factory.create_mapping_workflow(mapping_config, require_confirmation=not args.yes)
                try:
                    print(workflow.run())
                finally:
                    workflow.close()
                return 0
            stage = _simulated_stage(devices_config)
            if args.assume_user_zeroed:
                from lab_auto.devices.waynelabs_stage import AxisState

                for axis in ("x", "y"):
                    stage.ledger.states[axis] = AxisState.USER_ZEROED
                    stage.ledger.position_um[axis] = 0.0
            raman = RamanWorkflow.dry_run(workflow_config) if mode is RuntimeMode.DRY_RUN else RamanWorkflow.simulated(workflow_config)
            mapping_workflow = MappingWorkflow(
                config=mapping_config,
                stage=stage,
                point_runner=RamanPointRunner(raman, require_confirmation=not args.yes),
                dry_run=mode is RuntimeMode.DRY_RUN,
            )
            if mode is RuntimeMode.DRY_RUN:
                for action in mapping_workflow.plan_actions():
                    print(action)
            else:
                print(mapping_workflow.run())
            return 0
```

- [ ] **Step 7: Run focused CLI tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py tests/test_real_workflow_cli.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add src/lab_auto/cli.py src/lab_auto/devices/factory.py src/lab_auto/workflow/mapping.py tests/test_cli.py tests/test_real_workflow_cli.py
git commit -m "feat(mapping): wire mapping workflow cli"
```

---

## Task 6: Mapping Acceptance Docs and Full Verification

**Files:**
- Create: `docs/phase2-mapping-hardware-acceptance.md`
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-06-09-lab-automation-phase2-scope.md`

- [ ] **Step 1: Create hardware acceptance checklist**

Create `docs/phase2-mapping-hardware-acceptance.md`:

````markdown
# Phase 2 M2 Mapping Workflow — Hardware Acceptance

Run on the Windows 64-bit lab computer only, after dry-run and simulated tests pass.

## Preflight

1. Complete Phase 1 hardware acceptance for stage, spectrometer, and camera.
2. Complete Phase 2 M1 PWM light acceptance if `light.type: pwm_modbus` is used.
3. Confirm X/Y axis direction and effective resolution with 老师 / 厂家.
4. Confirm the configured X/Y grid remains inside soft limits.
5. Home or set-zero X and Y before running Mapping.

## Commands

```bash
ramanctl stage home --config configs/devices.real.yaml --real --axis x --direction negative --speed 8 --yes
ramanctl stage home --config configs/devices.real.yaml --real --axis y --direction negative --speed 8 --yes
ramanctl mapping run --config configs/mapping.real.yaml --real --yes
```

## Pass Criteria

- Mapping refuses to start when X or Y is `unknown`.
- Every point move stays within configured soft limits.
- Each point writes a stable point directory and manifest entry.
- Resume skips only points marked `complete`.
- Any failure records the failed point and error in the manifest.
- The workflow closes stage, spectrometer, camera, and light through the `finally` path.
- Laser safety behavior is unchanged from single-point workflow and M1 light acceptance.
````

- [ ] **Step 2: Update README and Phase 2 scope**

After M2 implementation, update:
- `README.md` current progress to include M2 code-complete and the new test count.
- `docs/superpowers/plans/2026-06-09-lab-automation-phase2-scope.md` table: mark M2 `代码完成；待真机验收`, and mark M3 as the next planning candidate.

- [ ] **Step 3: Run full verification**

Run:

```bash
.venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m lab_auto workflow single --config configs/single_point.example.yaml --dry-run
PYTHONPATH=src .venv/bin/python -m lab_auto mapping run --config configs/mapping.example.yaml --dry-run --assume-user-zeroed
git diff --check
```

Expected:
- All tests pass.
- Single-point dry-run prints the existing action sequence.
- Mapping dry-run prints `mapping_point:*`, `stage_move:*`, and single-point actions.
- `git diff --check` prints no whitespace errors.

- [ ] **Step 4: Commit docs**

```bash
git add docs/phase2-mapping-hardware-acceptance.md README.md docs/superpowers/plans/2026-06-09-lab-automation-phase2-scope.md
git commit -m "docs(mapping): add phase2 m2 hardware acceptance checklist"
```

---

## Final Verification

Run:

```bash
.venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m lab_auto workflow single --config configs/single_point.example.yaml --dry-run
PYTHONPATH=src .venv/bin/python -m lab_auto mapping run --config configs/mapping.example.yaml --dry-run --assume-user-zeroed
git status --short
```

Expected:
- Tests pass.
- Both dry-run commands exit 0.
- Worktree is clean except intentionally ignored runtime files.

## Self-Review

Spec coverage:
- Stage X/Y known-position gate: Task 1.
- Mapping grid scan: Tasks 2-4.
- Single-point reuse and light safety preservation: Tasks 4-5.
- Interruptible/resumable/auditable manifest: Tasks 3-4.
- Dry-run/simulated-first and real-mode explicit confirmation: Tasks 5-6.
- Deferred hardware acceptance: Task 6.

Type consistency:
- `MappingConfig.x` / `MappingConfig.y` use `MappingAxisConfig`.
- `MappingPoint.point_id` is used consistently by output directories and manifest keys.
- `MappingWorkflow.plan_actions()` is dry-run only; `MappingWorkflow.run()` writes manifest entries.

Intentional exclusions:
- No sample recognition, no post-processing enhancement, no daemon/session, no Agent tool schema, no HTTP light backend.
- No serpentine order in M2; row-major is the only supported scan order.
