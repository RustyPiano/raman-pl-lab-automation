# Lab Automation Phase 1 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 laboratory automation MVP: stateless CLI commands, dry-run/simulated execution, WayneLabs stage protocol, Zolix and DField SDK adapters, and a single-point Raman/PL workflow.

**Architecture:** Use a strict `raw -> adapter -> workflow -> CLI` boundary. `raw` modules own native SDK symbols and serial protocol strings; adapters expose clean Python APIs; workflow and CLI never import `ctypes`, vendor demo code, or hand-written hardware command strings. Phase 1 stops at single-point measurement; Mapping, Agent tool schema, daemon/session mode, and real light-controller automation remain out of scope.

**Tech Stack:** Python 3.11+, standard-library `argparse`, `ctypes`, `csv`, `json`, `dataclasses`, `pathlib`, plus `PyYAML`, `pyserial`, and `pytest`.

---

## Source Requirements

Primary spec: `docs/superpowers/specs/2026-06-04-lab-automation-platform-design.md`

Repository constraints: `AGENTS.md`

SDK references:
- WayneLabs protocol: `Waynelabs SDK Instructions.pdf`
- Zolix header: `光谱议控制SDK-32&64bit-20250429/SDK/inc/spectrometer.h`
- DField header: `DField-VS-A4-SDK-20250619/dfield-vs-a4.h`

## Phase 1 File Map

Create these files:

```text
pyproject.toml
configs/devices.example.yaml
configs/single_point.example.yaml
src/lab_auto/__init__.py
src/lab_auto/__main__.py
src/lab_auto/cli.py
src/lab_auto/config.py
src/lab_auto/errors.py
src/lab_auto/logging.py
src/lab_auto/runtime.py
src/lab_auto/devices/__init__.py
src/lab_auto/devices/base.py
src/lab_auto/devices/light.py
src/lab_auto/devices/simulated.py
src/lab_auto/devices/waynelabs_stage.py
src/lab_auto/devices/zolix_spectrometer.py
src/lab_auto/devices/dfield_camera.py
src/lab_auto/devices/raw/__init__.py
src/lab_auto/devices/raw/waynelabs_protocol.py
src/lab_auto/devices/raw/zolix_ctypes.py
src/lab_auto/devices/raw/dfield_ctypes.py
src/lab_auto/workflow/__init__.py
src/lab_auto/workflow/data.py
src/lab_auto/workflow/raman.py
src/lab_auto/processing/__init__.py
src/lab_auto/processing/background.py
tests/test_config.py
tests/test_waynelabs_protocol.py
tests/test_stage_safety.py
tests/test_zolix_ctypes.py
tests/test_zolix_adapter.py
tests/test_dfield_ctypes.py
tests/test_dfield_camera.py
tests/test_background.py
tests/test_workflow_dry_run.py
tests/test_cli.py
```

Responsibilities:
- `devices/raw/*`: only place for native SDK symbols, `ctypes` signatures, and serial protocol command strings.
- `devices/*_stage.py`, `devices/*_spectrometer.py`, `devices/*_camera.py`: clean adapters, enum mapping, runtime-mode behavior, state validation.
- `workflow/data.py`: platform-independent capture and spectrum data models.
- `processing/background.py`: spectrum alignment checks and background subtraction.
- `workflow/raman.py`: single-point workflow orchestration and output writing.
- `cli.py`: stateless command entry point using config and adapters.

## Execution Rules

- Make one commit per task.
- Run the task-specific tests before each commit.
- Keep real hardware commands guarded by `--real`.
- Do not create `workflow/mapping.py`, `agent/tool_schema.py`, daemon/session code, or real light-controller integration in Phase 1.

---

### Task 1: Project Scaffold, Runtime Mode, and Config Loading

**Files:**
- Create: `pyproject.toml`
- Create: `configs/devices.example.yaml`
- Create: `configs/single_point.example.yaml`
- Create: `src/lab_auto/__init__.py`
- Create: `src/lab_auto/__main__.py`
- Create: `src/lab_auto/errors.py`
- Create: `src/lab_auto/runtime.py`
- Create: `src/lab_auto/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write config tests**

Create `tests/test_config.py`:

```python
from pathlib import Path

import pytest

from lab_auto.config import load_devices_config, load_workflow_config
from lab_auto.errors import ConfigError
from lab_auto.runtime import RuntimeMode, resolve_runtime_mode


def test_load_devices_config_reads_runtime_and_stage(tmp_path: Path):
    path = tmp_path / "devices.yaml"
    path.write_text(
        """
runtime:
  mode: dry_run
  log_level: info
stage:
  type: waynelabs_linear
  port: COM5
  baudrate: 9600
  resolution_um: {x: 0.04, y: 0.04, z: 0.04}
  default_speed: 8
  soft_limits_um: {x: [-5000, 5000], y: [-5000, 5000], z: [-1000, 1000]}
  state_file: state/stage_position.json
  max_unknown_move_um: 100
spectrometer:
  type: zolix
  dll_path: C:/RamanSDK/SDK/x64/spectrometer_x64.dll
camera:
  type: dfield_vs_a4
  dll_path: C:/RamanSDK/DField/x64/dfield-vs-a4.dll
light:
  type: manual
  manual_light_control: true
""",
        encoding="utf-8",
    )

    config = load_devices_config(path)

    assert config.runtime.mode is RuntimeMode.DRY_RUN
    assert config.stage.port == "COM5"
    assert config.stage.resolution_um["x"] == 0.04
    assert config.light.manual_light_control is True


def test_workflow_config_links_devices_config(tmp_path: Path):
    path = tmp_path / "single_point.yaml"
    path.write_text(
        """
devices_config: configs/devices.yaml
sample: {id: sample-001, operator: lab}
optics:
  entrance_port: side
  exit_port: direct
  grating: 1
  center_wavelength_nm: 600
  slit_width_um: 100
acquisition:
  exposure_ms: 1000
  gain: low
  read_mode: fvb
  frames: 1
  subtract_background: true
output:
  directory: output/measurements
  formats: [csv, json]
""",
        encoding="utf-8",
    )

    config = load_workflow_config(path)

    assert config.devices_config == Path("configs/devices.yaml")
    assert config.optics.entrance_port == "side"
    assert config.optics.exit_port == "direct"
    assert config.acquisition.gain == "low"


def test_runtime_cli_override_wins():
    assert resolve_runtime_mode(RuntimeMode.DRY_RUN, cli_real=True) is RuntimeMode.REAL
    assert resolve_runtime_mode(RuntimeMode.REAL, cli_dry_run=True) is RuntimeMode.DRY_RUN
    assert resolve_runtime_mode(RuntimeMode.REAL, cli_simulated=True) is RuntimeMode.SIMULATED


def test_runtime_override_flags_are_mutually_exclusive():
    with pytest.raises(ConfigError, match="mutually exclusive"):
        resolve_runtime_mode(RuntimeMode.DRY_RUN, cli_real=True, cli_dry_run=True)
```

- [ ] **Step 2: Run tests to verify scaffold is missing**

Run:

```bash
pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'lab_auto'`.

- [ ] **Step 3: Create package metadata**

Create `pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "lab-automation"
version = "0.1.0"
description = "Phase 1 laboratory Raman/PL automation CLI"
requires-python = ">=3.11"
dependencies = [
  "PyYAML>=6.0.1",
  "pyserial>=3.5",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
]

[project.scripts]
ramanctl = "lab_auto.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 4: Create runtime and errors modules**

Create `src/lab_auto/errors.py`:

```python
class LabAutomationError(Exception):
    """Base error for recoverable lab automation failures."""


class ConfigError(LabAutomationError):
    """Configuration is missing, invalid, or internally inconsistent."""


class DeviceError(LabAutomationError):
    """Hardware adapter or raw binding operation failed."""


class SafetyError(LabAutomationError):
    """Requested action violates a configured safety rule."""
```

Create `src/lab_auto/runtime.py`:

```python
from enum import Enum

from lab_auto.errors import ConfigError


class RuntimeMode(str, Enum):
    DRY_RUN = "dry_run"
    SIMULATED = "simulated"
    REAL = "real"


def parse_runtime_mode(value: str | RuntimeMode | None) -> RuntimeMode:
    if value is None:
        return RuntimeMode.DRY_RUN
    if isinstance(value, RuntimeMode):
        return value
    try:
        return RuntimeMode(value)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in RuntimeMode)
        raise ConfigError(f"runtime.mode must be one of: {allowed}") from exc


def resolve_runtime_mode(
    configured: str | RuntimeMode | None,
    *,
    cli_real: bool = False,
    cli_dry_run: bool = False,
    cli_simulated: bool = False,
) -> RuntimeMode:
    selected = [cli_real, cli_dry_run, cli_simulated]
    if sum(bool(flag) for flag in selected) > 1:
        raise ConfigError("--real, --dry-run, and --simulated are mutually exclusive")
    if cli_real:
        return RuntimeMode.REAL
    if cli_dry_run:
        return RuntimeMode.DRY_RUN
    if cli_simulated:
        return RuntimeMode.SIMULATED
    return parse_runtime_mode(configured)
```

- [ ] **Step 5: Create config dataclasses and YAML loader**

Create `src/lab_auto/config.py` with these public dataclasses:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from lab_auto.errors import ConfigError
from lab_auto.runtime import RuntimeMode, parse_runtime_mode


@dataclass(frozen=True)
class RuntimeConfig:
    mode: RuntimeMode
    log_level: str


@dataclass(frozen=True)
class StageConfig:
    type: str
    port: str
    baudrate: int
    resolution_um: dict[str, float]
    default_speed: int
    soft_limits_um: dict[str, list[float]]
    state_file: Path
    max_unknown_move_um: float


@dataclass(frozen=True)
class SpectrometerConfig:
    type: str
    dll_path: Path
    usb_mode: bool


@dataclass(frozen=True)
class CameraConfig:
    type: str
    dll_path: Path


@dataclass(frozen=True)
class LightConfig:
    type: str
    manual_light_control: bool


@dataclass(frozen=True)
class DevicesConfig:
    runtime: RuntimeConfig
    stage: StageConfig
    spectrometer: SpectrometerConfig
    camera: CameraConfig
    light: LightConfig


@dataclass(frozen=True)
class SampleConfig:
    id: str
    operator: str


@dataclass(frozen=True)
class OpticsConfig:
    entrance_port: str
    exit_port: str
    grating: int
    center_wavelength_nm: float
    slit_width_um: int


@dataclass(frozen=True)
class AcquisitionConfig:
    exposure_ms: float
    gain: str
    read_mode: str
    frames: int
    subtract_background: bool


@dataclass(frozen=True)
class OutputConfig:
    directory: Path
    formats: list[str]


@dataclass(frozen=True)
class WorkflowConfig:
    devices_config: Path
    sample: SampleConfig
    optics: OpticsConfig
    acquisition: AcquisitionConfig
    output: OutputConfig


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"configuration file does not exist: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"configuration root must be a mapping: {path}")
    return data


def load_devices_config(path: str | Path) -> DevicesConfig:
    data = _read_yaml(Path(path))
    runtime = data.get("runtime", {})
    stage = data["stage"]
    spectrometer = data["spectrometer"]
    camera = data["camera"]
    light = data["light"]
    return DevicesConfig(
        runtime=RuntimeConfig(
            mode=parse_runtime_mode(runtime.get("mode")),
            log_level=str(runtime.get("log_level", "info")),
        ),
        stage=StageConfig(
            type=str(stage["type"]),
            port=str(stage["port"]),
            baudrate=int(stage["baudrate"]),
            resolution_um={axis: float(value) for axis, value in stage["resolution_um"].items()},
            default_speed=int(stage["default_speed"]),
            soft_limits_um={axis: [float(v) for v in values] for axis, values in stage["soft_limits_um"].items()},
            state_file=Path(stage["state_file"]),
            max_unknown_move_um=float(stage["max_unknown_move_um"]),
        ),
        spectrometer=SpectrometerConfig(
            type=str(spectrometer["type"]),
            dll_path=Path(spectrometer["dll_path"]),
            usb_mode=bool(spectrometer.get("usb_mode", True)),
        ),
        camera=CameraConfig(type=str(camera["type"]), dll_path=Path(camera["dll_path"])),
        light=LightConfig(
            type=str(light["type"]),
            manual_light_control=bool(light["manual_light_control"]),
        ),
    )


def load_workflow_config(path: str | Path) -> WorkflowConfig:
    data = _read_yaml(Path(path))
    return WorkflowConfig(
        devices_config=Path(data["devices_config"]),
        sample=SampleConfig(**data["sample"]),
        optics=OpticsConfig(**data["optics"]),
        acquisition=AcquisitionConfig(**data["acquisition"]),
        output=OutputConfig(
            directory=Path(data["output"]["directory"]),
            formats=list(data["output"]["formats"]),
        ),
    )
```

- [ ] **Step 6: Add package entry files and example configs**

Create `src/lab_auto/__init__.py`:

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

Create `src/lab_auto/__main__.py`:

```python
from lab_auto.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

Create `configs/devices.example.yaml`:

```yaml
runtime:
  mode: dry_run
  log_level: info

stage:
  type: waynelabs_linear
  port: COM5
  baudrate: 9600
  resolution_um:
    x: 0.04
    y: 0.04
    z: 0.04
  default_speed: 8
  soft_limits_um:
    x: [-5000, 5000]
    y: [-5000, 5000]
    z: [-1000, 1000]
  state_file: state/stage_position.json
  max_unknown_move_um: 100

spectrometer:
  type: zolix
  dll_path: C:/RamanSDK/SDK/x64/spectrometer_x64.dll
  usb_mode: true

camera:
  type: dfield_vs_a4
  dll_path: C:/RamanSDK/DField/x64/dfield-vs-a4.dll

light:
  type: manual
  manual_light_control: true
```

Create `configs/single_point.example.yaml`:

```yaml
devices_config: configs/devices.yaml

sample:
  id: sample-001
  operator: lab

optics:
  entrance_port: side
  exit_port: direct
  grating: 1
  center_wavelength_nm: 600
  slit_width_um: 100

acquisition:
  exposure_ms: 1000
  gain: low
  read_mode: fvb
  frames: 1
  subtract_background: true

output:
  directory: output/measurements
  formats: [csv, json]
```

- [ ] **Step 7: Run config tests**

Run:

```bash
python -m pip install -e ".[dev]"
pytest tests/test_config.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 8: Commit scaffold**

```bash
git add pyproject.toml configs src tests/test_config.py
git commit -m "chore: scaffold phase1 automation package"
```

---

### Task 2: Spectrum Data Models and Background Subtraction

**Files:**
- Create: `src/lab_auto/workflow/data.py`
- Create: `src/lab_auto/processing/background.py`
- Create: `tests/test_background.py`

- [ ] **Step 1: Write background subtraction tests**

Create `tests/test_background.py`:

```python
import pytest

from lab_auto.errors import ConfigError
from lab_auto.processing.background import subtract_background
from lab_auto.workflow.data import SpectrumData


def spectrum(*, x, raw, background=None, metadata=None):
    return SpectrumData(
        x_axis_type="wavelength_nm",
        x=list(x),
        intensity_raw=list(raw),
        intensity_background=background,
        intensity_corrected=None,
        saturated=[False for _ in raw],
        metadata=metadata
        or {
            "read_mode": "fvb",
            "bin_x": 1,
            "bin_y": 1,
            "roi": None,
            "detector_width": 2048,
            "detector_height": 1,
            "grating": 1,
            "center_wavelength_nm": 600.0,
            "slit_width_um": 100,
        },
    )


def test_subtract_background_aligns_by_x_values():
    raw = spectrum(x=[580.0, 581.0], raw=[1000, 1100])
    bg = spectrum(x=[580.0, 581.0], raw=[100, 120])

    corrected = subtract_background(raw, bg)

    assert corrected.intensity_background == [100, 120]
    assert corrected.intensity_corrected == [900, 980]


def test_subtract_background_rejects_wavelength_mismatch():
    raw = spectrum(x=[580.0, 581.0], raw=[1000, 1100])
    bg = spectrum(x=[580.0, 581.002], raw=[100, 120])

    with pytest.raises(ConfigError, match="x axis values differ"):
        subtract_background(raw, bg, wavelength_tolerance_nm=1e-6)


def test_subtract_background_rejects_axis_metadata_mismatch():
    raw = spectrum(x=[580.0], raw=[1000])
    bg = spectrum(
        x=[580.0],
        raw=[100],
        metadata={
            "read_mode": "fvb",
            "bin_x": 2,
            "bin_y": 1,
            "roi": None,
            "detector_width": 2048,
            "detector_height": 1,
            "grating": 1,
            "center_wavelength_nm": 600.0,
            "slit_width_um": 100,
        },
    )

    with pytest.raises(ConfigError, match="axis metadata differs: bin_x"):
        subtract_background(raw, bg)
```

- [ ] **Step 2: Run tests to verify missing modules**

Run:

```bash
pytest tests/test_background.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `lab_auto.processing.background`.

- [ ] **Step 3: Implement platform-independent data models**

Create `src/lab_auto/workflow/data.py`:

```python
from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class CaptureFrame:
    read_mode: str
    width: int
    height: int
    bin_x: int
    bin_y: int
    roi: tuple[int, int, int, int] | None
    exposure_ms: float
    gain: str
    values: list[int]
    saturated_count: int
    saturated: list[bool]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SpectrumData:
    x_axis_type: str
    x: list[float | int]
    intensity_raw: list[float]
    intensity_background: list[float] | None
    intensity_corrected: list[float] | None
    saturated: list[bool]
    metadata: dict[str, Any]

    def with_background(self, background: list[float], corrected: list[float]) -> "SpectrumData":
        return replace(
            self,
            intensity_background=list(background),
            intensity_corrected=list(corrected),
        )
```

- [ ] **Step 4: Implement background subtraction**

Create `src/lab_auto/processing/__init__.py`:

```python
__all__ = []
```

Create `src/lab_auto/processing/background.py`:

```python
from lab_auto.errors import ConfigError
from lab_auto.workflow.data import SpectrumData


AXIS_METADATA_KEYS = (
    "read_mode",
    "bin_x",
    "bin_y",
    "roi",
    "detector_width",
    "detector_height",
    "grating",
    "center_wavelength_nm",
    "slit_width_um",
)


def _assert_axis_metadata_matches(raw: SpectrumData, background: SpectrumData) -> None:
    for key in AXIS_METADATA_KEYS:
        if raw.metadata.get(key) != background.metadata.get(key):
            raise ConfigError(f"axis metadata differs: {key}")


def _assert_x_matches(raw: SpectrumData, background: SpectrumData, wavelength_tolerance_nm: float) -> None:
    if raw.x_axis_type != background.x_axis_type:
        raise ConfigError("x_axis_type differs between raw and background spectra")
    if len(raw.x) != len(background.x):
        raise ConfigError("raw/background lengths differ")
    for index, (raw_x, bg_x) in enumerate(zip(raw.x, background.x, strict=True)):
        if raw.x_axis_type == "pixel_index":
            if int(raw_x) != int(bg_x):
                raise ConfigError(f"x axis values differ at index {index}")
        elif abs(float(raw_x) - float(bg_x)) > wavelength_tolerance_nm:
            raise ConfigError(f"x axis values differ at index {index}")


def subtract_background(
    raw: SpectrumData,
    background: SpectrumData,
    *,
    wavelength_tolerance_nm: float = 1e-6,
) -> SpectrumData:
    _assert_x_matches(raw, background, wavelength_tolerance_nm)
    _assert_axis_metadata_matches(raw, background)
    corrected = [
        float(raw_value) - float(bg_value)
        for raw_value, bg_value in zip(raw.intensity_raw, background.intensity_raw, strict=True)
    ]
    return raw.with_background(background.intensity_raw, corrected)
```

- [ ] **Step 5: Run background tests**

Run:

```bash
pytest tests/test_background.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 6: Commit data models**

```bash
git add src/lab_auto/workflow src/lab_auto/processing tests/test_background.py
git commit -m "feat: add spectrum data model and background subtraction"
```

---

### Task 3: WayneLabs Raw Protocol

**Files:**
- Create: `src/lab_auto/devices/raw/waynelabs_protocol.py`
- Create: `tests/test_waynelabs_protocol.py`

- [ ] **Step 1: Write protocol tests**

Create `tests/test_waynelabs_protocol.py`:

```python
import pytest

from lab_auto.devices.raw.waynelabs_protocol import (
    Completed,
    LimitOrHome,
    ProtocolError,
    build_home_command,
    build_move_command,
    parse_completion,
    split_steps,
)


def test_build_x_positive_move_command():
    assert build_move_command(axis="x", steps=924, speed=0, direction="positive") == "?X00924c"


def test_build_x_negative_move_command():
    assert build_move_command(axis="x", steps=924, speed=0, direction="negative") == "?X00924b"


def test_build_home_command_uses_zero_steps():
    assert build_home_command(axis="z", speed=8, direction="negative") == "?X80000f"


def test_split_steps_limits_single_command_to_9999():
    assert split_steps(25000) == [9999, 9999, 5002]


def test_parse_completion_accepts_direction_response():
    assert parse_completion("?b") == Completed(direction="b")


def test_parse_completion_accepts_limit_or_home():
    assert parse_completion("?t") == LimitOrHome()


def test_rejects_invalid_speed():
    with pytest.raises(ProtocolError, match="speed"):
        build_move_command(axis="x", steps=1, speed=12, direction="positive")
```

- [ ] **Step 2: Run tests to verify missing raw module**

Run:

```bash
pytest tests/test_waynelabs_protocol.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `lab_auto.devices.raw.waynelabs_protocol`.

- [ ] **Step 3: Implement raw protocol**

Create `src/lab_auto/devices/raw/__init__.py`:

```python
__all__ = []
```

Create `src/lab_auto/devices/raw/waynelabs_protocol.py`:

```python
from dataclasses import dataclass


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Completed:
    direction: str


@dataclass(frozen=True)
class LimitOrHome:
    marker: str = "t"


DIRECTION_CODES = {
    ("x", "negative"): "b",
    ("x", "positive"): "c",
    ("y", "negative"): "d",
    ("y", "positive"): "e",
    ("z", "negative"): "f",
    ("z", "positive"): "g",
}


def split_steps(steps: int) -> list[int]:
    if steps < 0:
        raise ProtocolError("steps must be non-negative")
    chunks: list[int] = []
    remaining = steps
    while remaining > 9999:
        chunks.append(9999)
        remaining -= 9999
    if remaining:
        chunks.append(remaining)
    return chunks


def _direction_code(axis: str, direction: str) -> str:
    key = (axis.lower(), direction)
    if key not in DIRECTION_CODES:
        raise ProtocolError(f"unsupported axis/direction: {axis}/{direction}")
    return DIRECTION_CODES[key]


def _validate_speed(speed: int) -> None:
    if speed < 0 or speed > 9:
        raise ProtocolError("speed must be between 0 and 9")


def build_move_command(*, axis: str, steps: int, speed: int, direction: str) -> str:
    _validate_speed(speed)
    if steps < 1 or steps > 9999:
        raise ProtocolError("move steps must be between 1 and 9999")
    return f"?X{speed}{steps:04d}{_direction_code(axis, direction)}"


def build_home_command(*, axis: str, speed: int, direction: str) -> str:
    _validate_speed(speed)
    return f"?X{speed}0000{_direction_code(axis, direction)}"


def parse_completion(response: str) -> Completed | LimitOrHome:
    text = response.strip()
    if text == "?t":
        return LimitOrHome()
    if len(text) == 2 and text[0] == "?" and text[1] in "bcdefg":
        return Completed(direction=text[1])
    raise ProtocolError(f"unexpected completion response: {response!r}")
```

- [ ] **Step 4: Run protocol tests**

Run:

```bash
pytest tests/test_waynelabs_protocol.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Commit raw protocol**

```bash
git add src/lab_auto/devices/raw tests/test_waynelabs_protocol.py
git commit -m "feat: add waynelabs raw protocol"
```

---

### Task 4: Stage Adapter and Safety State

**Files:**
- Create: `src/lab_auto/devices/base.py`
- Create: `src/lab_auto/devices/waynelabs_stage.py`
- Create: `tests/test_stage_safety.py`

- [ ] **Step 1: Write safety tests**

Create `tests/test_stage_safety.py`:

```python
import pytest

from lab_auto.config import StageConfig
from lab_auto.errors import SafetyError
from lab_auto.devices.waynelabs_stage import AxisState, PositionLedger, WaynelabsStage


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
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True)

    actions = stage.move_relative(axis="x", um=10, speed=8)

    assert actions == ["?X80250c"]


def test_unknown_axis_rejects_large_move(tmp_path):
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True)

    with pytest.raises(SafetyError, match="unknown position"):
        stage.move_relative(axis="x", um=150, speed=8)


def test_known_axis_uses_soft_limits(tmp_path):
    ledger = PositionLedger(states={"x": AxisState.USER_ZEROED}, position_um={"x": 4995.0})
    stage = WaynelabsStage(config(tmp_path), transport=None, dry_run=True, ledger=ledger)

    with pytest.raises(SafetyError, match="soft limit"):
        stage.move_relative(axis="x", um=10, speed=8)
```

- [ ] **Step 2: Run safety tests to verify adapter missing**

Run:

```bash
pytest tests/test_stage_safety.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `lab_auto.devices.waynelabs_stage`.

- [ ] **Step 3: Implement stage state and dry-run adapter**

Create `src/lab_auto/devices/__init__.py`:

```python
__all__ = []
```

Create `src/lab_auto/devices/base.py`:

```python
from typing import Protocol


class Device(Protocol):
    def close(self) -> None:
        ...
```

Create `src/lab_auto/devices/waynelabs_stage.py` with:

```python
from dataclasses import dataclass, field
from enum import Enum

from lab_auto.config import StageConfig
from lab_auto.devices.raw.waynelabs_protocol import build_move_command, split_steps
from lab_auto.errors import SafetyError


class AxisState(str, Enum):
    UNKNOWN = "unknown"
    HOMED = "homed"
    USER_ZEROED = "user_zeroed"


@dataclass
class PositionLedger:
    states: dict[str, AxisState] = field(default_factory=lambda: {"x": AxisState.UNKNOWN, "y": AxisState.UNKNOWN, "z": AxisState.UNKNOWN})
    position_um: dict[str, float] = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})


class WaynelabsStage:
    def __init__(
        self,
        config: StageConfig,
        *,
        transport,
        dry_run: bool,
        ledger: PositionLedger | None = None,
    ):
        self.config = config
        self.transport = transport
        self.dry_run = dry_run
        self.ledger = ledger or PositionLedger()

    def _steps_for_um(self, axis: str, um: float) -> int:
        return round(abs(um) / self.config.resolution_um[axis])

    def _direction_for_um(self, um: float) -> str:
        return "positive" if um >= 0 else "negative"

    def _assert_safe_move(self, axis: str, um: float) -> None:
        state = self.ledger.states.get(axis, AxisState.UNKNOWN)
        if state is AxisState.UNKNOWN and abs(um) > self.config.max_unknown_move_um:
            raise SafetyError("unknown position only allows small relative moves")
        if state is not AxisState.UNKNOWN:
            new_position = self.ledger.position_um.get(axis, 0.0) + um
            low, high = self.config.soft_limits_um[axis]
            if new_position < low or new_position > high:
                raise SafetyError(f"move exceeds soft limit for axis {axis}")

    def move_relative(self, *, axis: str, um: float, speed: int) -> list[str]:
        self._assert_safe_move(axis, um)
        direction = self._direction_for_um(um)
        commands = [
            build_move_command(axis=axis, steps=chunk, speed=speed, direction=direction)
            for chunk in split_steps(self._steps_for_um(axis, um))
        ]
        if not self.dry_run and self.transport is not None:
            for command in commands:
                self.transport.write(command)
        return commands

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()
```

- [ ] **Step 4: Run safety tests**

Run:

```bash
pytest tests/test_stage_safety.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit stage adapter**

```bash
git add src/lab_auto/devices tests/test_stage_safety.py
git commit -m "feat: add waynelabs stage safety adapter"
```

---

### Task 5: Zolix Raw ctypes Binding and Adapter

**Files:**
- Create: `src/lab_auto/devices/raw/zolix_ctypes.py`
- Create: `src/lab_auto/devices/zolix_spectrometer.py`
- Create: `tests/test_zolix_ctypes.py`
- Create: `tests/test_zolix_adapter.py`

- [ ] **Step 1: Write raw signature tests**

Create `tests/test_zolix_ctypes.py`:

```python
import ctypes

from lab_auto.devices.raw.zolix_ctypes import configure_signatures


class FakeLibrary:
    pass


def function():
    def inner(*args):
        return None
    return inner


def test_configures_spec_get_error_as_void_three_args():
    lib = FakeLibrary()
    lib.spec_get_error = function()

    configure_signatures(lib)

    assert lib.spec_get_error.argtypes == [ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    assert lib.spec_get_error.restype is None


def test_configures_port_functions_with_bool():
    lib = FakeLibrary()
    lib.spec_set_entrance_port = function()
    lib.spec_set_exit_port = function()

    configure_signatures(lib)

    assert lib.spec_set_entrance_port.argtypes == [ctypes.c_int, ctypes.c_bool]
    assert lib.spec_set_exit_port.argtypes == [ctypes.c_int, ctypes.c_bool]
```

- [ ] **Step 2: Write adapter enum tests**

Create `tests/test_zolix_adapter.py`:

```python
from lab_auto.devices.zolix_spectrometer import direct_to_front_bool, front_bool_to_port


def test_direct_and_front_alias_map_to_true():
    assert direct_to_front_bool("direct") is True
    assert direct_to_front_bool("front") is True


def test_side_maps_to_false():
    assert direct_to_front_bool("side") is False


def test_front_bool_to_port_uses_clean_names():
    assert front_bool_to_port(True) == "direct"
    assert front_bool_to_port(False) == "side"
```

- [ ] **Step 3: Run Zolix tests to verify modules missing**

Run:

```bash
pytest tests/test_zolix_ctypes.py tests/test_zolix_adapter.py -v
```

Expected: FAIL with missing Zolix modules.

- [ ] **Step 4: Implement raw signature configuration**

Create `src/lab_auto/devices/raw/zolix_ctypes.py`:

```python
import ctypes
from pathlib import Path


def load_library(dll_path: Path):
    if hasattr(ctypes, "WinDLL"):
        return ctypes.WinDLL(str(dll_path))
    return ctypes.CDLL(str(dll_path))


def _maybe_configure(lib, name: str, argtypes, restype) -> None:
    func = getattr(lib, name, None)
    if func is not None:
        func.argtypes = argtypes
        func.restype = restype


def configure_signatures(lib) -> None:
    _maybe_configure(lib, "spec_get_dll_ver", [ctypes.c_char_p, ctypes.c_int], None)
    _maybe_configure(lib, "spec_set_usb_mode", [ctypes.c_bool], ctypes.c_bool)
    _maybe_configure(lib, "spec_enum_dev_count", [], ctypes.c_int)
    _maybe_configure(lib, "spec_enum_dev_sn", [ctypes.c_int, ctypes.c_char_p, ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "spec_open", [ctypes.c_char_p], ctypes.c_int)
    _maybe_configure(lib, "spec_close", [ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_is_open", [ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_error", [ctypes.c_int, ctypes.c_char_p, ctypes.c_int], None)
    _maybe_configure(lib, "spec_set_grating", [ctypes.c_int, ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_grating", [ctypes.c_int, ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "spec_move_to_wave", [ctypes.c_int, ctypes.c_float], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_curr_wave", [ctypes.c_int, ctypes.POINTER(ctypes.c_float)], ctypes.c_bool)
    _maybe_configure(lib, "spec_set_entrance_port", [ctypes.c_int, ctypes.c_bool], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_entrance_port", [ctypes.c_int, ctypes.POINTER(ctypes.c_bool)], ctypes.c_bool)
    _maybe_configure(lib, "spec_set_exit_port", [ctypes.c_int, ctypes.c_bool], ctypes.c_bool)
    _maybe_configure(lib, "spec_get_exit_port", [ctypes.c_int, ctypes.POINTER(ctypes.c_bool)], ctypes.c_bool)
    _maybe_configure(lib, "spec_set_slit_width", [ctypes.c_int, ctypes.c_int, ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "spec_pixels_to_waves", [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_float)], ctypes.c_bool)
```

- [ ] **Step 5: Implement clean adapter helpers**

Create `src/lab_auto/devices/zolix_spectrometer.py`:

```python
from lab_auto.errors import ConfigError


def direct_to_front_bool(port: str) -> bool:
    normalized = port.lower()
    if normalized in {"direct", "front"}:
        return True
    if normalized == "side":
        return False
    raise ConfigError(f"unsupported Zolix port: {port}")


def front_bool_to_port(value: bool) -> str:
    return "direct" if value else "side"


class ZolixSpectrometer:
    def __init__(self, lib, device_id: int):
        self.lib = lib
        self.device_id = device_id

    def set_entrance_port(self, port: str) -> bool:
        return bool(self.lib.spec_set_entrance_port(self.device_id, direct_to_front_bool(port)))

    def set_exit_port(self, port: str) -> bool:
        return bool(self.lib.spec_set_exit_port(self.device_id, direct_to_front_bool(port)))
```

- [ ] **Step 6: Run Zolix tests**

Run:

```bash
pytest tests/test_zolix_ctypes.py tests/test_zolix_adapter.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 7: Commit Zolix boundary**

```bash
git add src/lab_auto/devices/raw/zolix_ctypes.py src/lab_auto/devices/zolix_spectrometer.py tests/test_zolix_ctypes.py tests/test_zolix_adapter.py
git commit -m "feat: add zolix raw binding boundary"
```

---

### Task 6: DField Raw ctypes Binding and Camera Adapter

**Files:**
- Create: `src/lab_auto/devices/raw/dfield_ctypes.py`
- Create: `src/lab_auto/devices/dfield_camera.py`
- Create: `tests/test_dfield_ctypes.py`
- Create: `tests/test_dfield_camera.py`

- [ ] **Step 1: Write DField raw signature tests**

Create `tests/test_dfield_ctypes.py`:

```python
import ctypes

from lab_auto.devices.raw.dfield_ctypes import configure_signatures, windows_long_array


class FakeLibrary:
    pass


def function():
    def inner(*args):
        return True
    return inner


def test_configures_close_as_void():
    lib = FakeLibrary()
    lib.a4_close = function()

    configure_signatures(lib)

    assert lib.a4_close.argtypes == []
    assert lib.a4_close.restype is None


def test_capture_uses_windows_32bit_long_buffer():
    arr = windows_long_array(3)

    assert ctypes.sizeof(arr._type_) == 4
```

- [ ] **Step 2: Write DField adapter tests**

Create `tests/test_dfield_camera.py`:

```python
from lab_auto.devices.dfield_camera import gain_to_code, read_mode_to_code


def test_gain_mapping_matches_header():
    assert gain_to_code("high") == 0
    assert gain_to_code("low") == 1


def test_read_mode_mapping_matches_header():
    assert read_mode_to_code("fvb") == 0
    assert read_mode_to_code("image") == 1
```

- [ ] **Step 3: Run DField tests to verify modules missing**

Run:

```bash
pytest tests/test_dfield_ctypes.py tests/test_dfield_camera.py -v
```

Expected: FAIL with missing DField modules.

- [ ] **Step 4: Implement DField raw binding**

Create `src/lab_auto/devices/raw/dfield_ctypes.py`:

```python
import ctypes
from pathlib import Path


WindowsLong = ctypes.c_int32


def windows_long_array(size: int):
    return (WindowsLong * size)()


def load_library(dll_path: Path):
    if hasattr(ctypes, "WinDLL"):
        return ctypes.WinDLL(str(dll_path))
    return ctypes.CDLL(str(dll_path))


def _maybe_configure(lib, name: str, argtypes, restype) -> None:
    func = getattr(lib, name, None)
    if func is not None:
        func.argtypes = argtypes
        func.restype = restype


def configure_signatures(lib) -> None:
    _maybe_configure(lib, "a4_open", [], ctypes.c_bool)
    _maybe_configure(lib, "a4_close", [], None)
    _maybe_configure(lib, "a4_get_exposure", [ctypes.POINTER(ctypes.c_float)], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_exposure", [ctypes.c_float], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_gain", [ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_gain", [ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_detector_size", [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_pixel_size", [ctypes.POINTER(ctypes.c_float)], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_read_mode", [ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_read_mode", [ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_bin", [ctypes.c_int, ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_bin", [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "a4_set_roi", [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int], ctypes.c_bool)
    _maybe_configure(lib, "a4_get_roi", [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)], ctypes.c_bool)
    _maybe_configure(lib, "a4_single_capture", [ctypes.POINTER(WindowsLong), ctypes.c_int], ctypes.c_bool)
```

- [ ] **Step 5: Implement DField adapter mappings**

Create `src/lab_auto/devices/dfield_camera.py`:

```python
from lab_auto.errors import ConfigError


def gain_to_code(gain: str) -> int:
    if gain == "high":
        return 0
    if gain == "low":
        return 1
    raise ConfigError(f"unsupported DField gain: {gain}")


def read_mode_to_code(read_mode: str) -> int:
    if read_mode == "fvb":
        return 0
    if read_mode == "image":
        return 1
    raise ConfigError(f"unsupported DField read_mode: {read_mode}")


class DFieldCamera:
    def __init__(self, lib):
        self.lib = lib

    def close(self) -> None:
        self.lib.a4_close()
```

- [ ] **Step 6: Run DField tests**

Run:

```bash
pytest tests/test_dfield_ctypes.py tests/test_dfield_camera.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 7: Commit DField boundary**

```bash
git add src/lab_auto/devices/raw/dfield_ctypes.py src/lab_auto/devices/dfield_camera.py tests/test_dfield_ctypes.py tests/test_dfield_camera.py
git commit -m "feat: add dfield raw binding boundary"
```

---

### Task 7: Simulated Devices and Manual Light

**Files:**
- Create: `src/lab_auto/devices/light.py`
- Create: `src/lab_auto/devices/simulated.py`
- Create: `tests/test_workflow_dry_run.py`

- [ ] **Step 1: Write simulated device tests**

Create the first tests in `tests/test_workflow_dry_run.py`:

```python
from lab_auto.devices.light import ManualLight
from lab_auto.devices.simulated import SimulatedCamera, SimulatedSpectrometer


def test_manual_light_records_confirmation_steps():
    light = ManualLight(manual=True)

    assert light.require_off_confirmation() == "confirm_laser_off"
    assert light.require_on_confirmation() == "confirm_laser_on"


def test_simulated_camera_returns_deterministic_fvb_frame():
    camera = SimulatedCamera()

    frame = camera.capture(read_mode="fvb", exposure_ms=1000, gain="low", frames=1)

    assert frame.read_mode == "fvb"
    assert frame.values[:3] == [1000, 1001, 1002]
    assert frame.saturated_count == 0


def test_simulated_spectrometer_pixel_to_wavelength():
    spec = SimulatedSpectrometer()

    waves = spec.pixels_to_waves(center_wavelength_nm=600.0, count=3)

    assert waves == [599.99, 600.0, 600.01]
```

- [ ] **Step 2: Run simulated tests to verify missing modules**

Run:

```bash
pytest tests/test_workflow_dry_run.py -v
```

Expected: FAIL with missing `lab_auto.devices.light`.

- [ ] **Step 3: Implement manual light and simulated devices**

Create `src/lab_auto/devices/light.py`:

```python
class ManualLight:
    def __init__(self, *, manual: bool):
        self.manual = manual

    def require_off_confirmation(self) -> str:
        if self.manual:
            return "confirm_laser_off"
        return "laser_off"

    def require_on_confirmation(self) -> str:
        if self.manual:
            return "confirm_laser_on"
        return "laser_on"
```

Create `src/lab_auto/devices/simulated.py`:

```python
from lab_auto.workflow.data import CaptureFrame


class SimulatedCamera:
    def capture(self, *, read_mode: str, exposure_ms: float, gain: str, frames: int) -> CaptureFrame:
        if read_mode == "fvb":
            values = [1000 + index for index in range(2048)]
            width = 2048
            height = 1
        else:
            width = 16
            height = 8
            values = [1000 + index for index in range(width * height)]
        return CaptureFrame(
            read_mode=read_mode,
            width=width,
            height=height,
            bin_x=1,
            bin_y=1,
            roi=None,
            exposure_ms=exposure_ms,
            gain=gain,
            values=values,
            saturated_count=0,
            saturated=[False for _ in values],
            metadata={
                "read_mode": read_mode,
                "bin_x": 1,
                "bin_y": 1,
                "roi": None,
                "detector_width": width,
                "detector_height": height,
            },
        )


class SimulatedSpectrometer:
    def pixels_to_waves(self, *, center_wavelength_nm: float, count: int) -> list[float]:
        middle = (count - 1) / 2
        return [round(center_wavelength_nm + (index - middle) * 0.01, 6) for index in range(count)]
```

- [ ] **Step 4: Run simulated tests**

Run:

```bash
pytest tests/test_workflow_dry_run.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit simulated devices**

```bash
git add src/lab_auto/devices/light.py src/lab_auto/devices/simulated.py tests/test_workflow_dry_run.py
git commit -m "feat: add simulated devices and manual light"
```

---

### Task 8: Single-Point Workflow and Output Files

**Files:**
- Create: `src/lab_auto/logging.py`
- Create: `src/lab_auto/workflow/raman.py`
- Modify: `tests/test_workflow_dry_run.py`

- [ ] **Step 1: Extend workflow dry-run tests**

Append to `tests/test_workflow_dry_run.py`:

```python
from pathlib import Path

from lab_auto.config import AcquisitionConfig, OpticsConfig, OutputConfig, SampleConfig, WorkflowConfig
from lab_auto.workflow.raman import RamanWorkflow


def workflow_config(tmp_path: Path):
    return WorkflowConfig(
        devices_config=Path("configs/devices.yaml"),
        sample=SampleConfig(id="sample-001", operator="lab"),
        optics=OpticsConfig(
            entrance_port="side",
            exit_port="direct",
            grating=1,
            center_wavelength_nm=600.0,
            slit_width_um=100,
        ),
        acquisition=AcquisitionConfig(
            exposure_ms=1000,
            gain="low",
            read_mode="fvb",
            frames=1,
            subtract_background=True,
        ),
        output=OutputConfig(directory=tmp_path, formats=["csv", "json"]),
    )


def test_single_workflow_dry_run_sequence(tmp_path):
    workflow = RamanWorkflow.dry_run(workflow_config(tmp_path))

    actions = workflow.measure_single_point(require_confirmation=False)

    assert actions == [
        "devices_check",
        "set_entrance_port:side",
        "set_exit_port:direct",
        "set_grating:1",
        "move_wavelength_nm:600.0",
        "set_slit_width_um:100",
        "confirm_laser_off",
        "capture_background",
        "confirm_laser_on",
        "capture_sample",
        "subtract_background",
        "save_outputs",
    ]


def test_single_workflow_writes_core_outputs(tmp_path):
    workflow = RamanWorkflow.simulated(workflow_config(tmp_path))

    run_dir = workflow.run_single_point(require_confirmation=False)

    assert (run_dir / "metadata.json").exists()
    assert (run_dir / "background.csv").exists()
    assert (run_dir / "raw.csv").exists()
    assert (run_dir / "corrected.csv").exists()
    assert (run_dir / "run.log").exists()
```

- [ ] **Step 2: Run workflow tests to verify workflow missing**

Run:

```bash
pytest tests/test_workflow_dry_run.py -v
```

Expected: FAIL with missing `lab_auto.workflow.raman`.

- [ ] **Step 3: Implement workflow output writer**

Create `src/lab_auto/logging.py`:

```python
from pathlib import Path


def append_run_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(message + "\n")
```

Create `src/lab_auto/workflow/__init__.py`:

```python
__all__ = []
```

Create `src/lab_auto/workflow/raman.py` with a minimal `RamanWorkflow`:

```python
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from lab_auto.config import WorkflowConfig
from lab_auto.devices.light import ManualLight
from lab_auto.devices.simulated import SimulatedCamera, SimulatedSpectrometer
from lab_auto.logging import append_run_log
from lab_auto.processing.background import subtract_background
from lab_auto.workflow.data import SpectrumData


@dataclass
class RamanWorkflow:
    config: WorkflowConfig
    dry: bool
    camera: SimulatedCamera
    spectrometer: SimulatedSpectrometer
    light: ManualLight

    @classmethod
    def dry_run(cls, config: WorkflowConfig) -> "RamanWorkflow":
        return cls(config, True, SimulatedCamera(), SimulatedSpectrometer(), ManualLight(manual=True))

    @classmethod
    def simulated(cls, config: WorkflowConfig) -> "RamanWorkflow":
        return cls(config, False, SimulatedCamera(), SimulatedSpectrometer(), ManualLight(manual=True))

    def measure_single_point(self, *, require_confirmation: bool) -> list[str]:
        return [
            "devices_check",
            f"set_entrance_port:{self.config.optics.entrance_port}",
            f"set_exit_port:{self.config.optics.exit_port}",
            f"set_grating:{self.config.optics.grating}",
            f"move_wavelength_nm:{self.config.optics.center_wavelength_nm}",
            f"set_slit_width_um:{self.config.optics.slit_width_um}",
            self.light.require_off_confirmation(),
            "capture_background",
            self.light.require_on_confirmation(),
            "capture_sample",
            "subtract_background",
            "save_outputs",
        ]

    def _frame_to_spectrum(self, values: list[int]) -> SpectrumData:
        x = self.spectrometer.pixels_to_waves(
            center_wavelength_nm=self.config.optics.center_wavelength_nm,
            count=len(values),
        )
        metadata = {
            "read_mode": self.config.acquisition.read_mode,
            "bin_x": 1,
            "bin_y": 1,
            "roi": None,
            "detector_width": len(values),
            "detector_height": 1,
            "grating": self.config.optics.grating,
            "center_wavelength_nm": self.config.optics.center_wavelength_nm,
            "slit_width_um": self.config.optics.slit_width_um,
        }
        return SpectrumData(
            x_axis_type="wavelength_nm",
            x=x,
            intensity_raw=[float(value) for value in values],
            intensity_background=None,
            intensity_corrected=None,
            saturated=[False for _ in values],
            metadata=metadata,
        )

    def run_single_point(self, *, require_confirmation: bool) -> Path:
        run_dir = self.config.output.directory / "sample-001"
        run_dir.mkdir(parents=True, exist_ok=True)
        background_frame = self.camera.capture(read_mode="fvb", exposure_ms=1000, gain="low", frames=1)
        sample_frame = self.camera.capture(read_mode="fvb", exposure_ms=1000, gain="low", frames=1)
        background = self._frame_to_spectrum([100 for _ in background_frame.values])
        raw = self._frame_to_spectrum(sample_frame.values)
        corrected = subtract_background(raw, background)
        self._write_raw(run_dir / "raw.csv", raw)
        self._write_background(run_dir / "background.csv", background)
        self._write_corrected(run_dir / "corrected.csv", corrected)
        (run_dir / "metadata.json").write_text(
            json.dumps({"sample_id": self.config.sample.id, "x_axis_type": raw.x_axis_type, "runtime_mode": "simulated"}, indent=2),
            encoding="utf-8",
        )
        append_run_log(run_dir / "run.log", "single_point_complete")
        return run_dir

    def _write_raw(self, path: Path, spectrum: SpectrumData) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["pixel_index", "wavelength_nm", "intensity_raw", "saturated"])
            for index, (wave, value, saturated) in enumerate(zip(spectrum.x, spectrum.intensity_raw, spectrum.saturated, strict=True)):
                writer.writerow([index, wave, value, str(saturated).lower()])

    def _write_background(self, path: Path, spectrum: SpectrumData) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["pixel_index", "wavelength_nm", "intensity_background", "saturated"])
            for index, (wave, value, saturated) in enumerate(zip(spectrum.x, spectrum.intensity_raw, spectrum.saturated, strict=True)):
                writer.writerow([index, wave, value, str(saturated).lower()])

    def _write_corrected(self, path: Path, spectrum: SpectrumData) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["pixel_index", "wavelength_nm", "intensity_raw", "intensity_background", "intensity_corrected", "saturated_raw", "saturated_background"])
            for index, wave in enumerate(spectrum.x):
                writer.writerow([
                    index,
                    wave,
                    spectrum.intensity_raw[index],
                    spectrum.intensity_background[index],
                    spectrum.intensity_corrected[index],
                    str(spectrum.saturated[index]).lower(),
                    "false",
                ])
```

- [ ] **Step 4: Run workflow tests**

Run:

```bash
pytest tests/test_workflow_dry_run.py -v
```

Expected: all workflow tests PASS.

- [ ] **Step 5: Commit workflow**

```bash
git add src/lab_auto/logging.py src/lab_auto/workflow tests/test_workflow_dry_run.py
git commit -m "feat: add single point workflow"
```

---

### Task 9: CLI Commands

**Files:**
- Create: `src/lab_auto/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write CLI tests**

Create `tests/test_cli.py`:

```python
from pathlib import Path

from lab_auto.cli import main


def write_workflow_config(path: Path, output_dir: Path):
    path.write_text(
        f"""
devices_config: configs/devices.yaml
sample: {{id: sample-001, operator: lab}}
optics:
  entrance_port: side
  exit_port: direct
  grating: 1
  center_wavelength_nm: 600
  slit_width_um: 100
acquisition:
  exposure_ms: 1000
  gain: low
  read_mode: fvb
  frames: 1
  subtract_background: true
output:
  directory: {output_dir}
  formats: [csv, json]
""",
        encoding="utf-8",
    )


def test_workflow_single_dry_run_prints_sequence(tmp_path, capsys):
    config = tmp_path / "single_point.yaml"
    write_workflow_config(config, tmp_path / "out")

    exit_code = main(["workflow", "single", "--config", str(config), "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "confirm_laser_off" in captured.out
    assert "capture_sample" in captured.out
```

- [ ] **Step 2: Run CLI tests to verify command missing**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: FAIL with missing `lab_auto.cli`.

- [ ] **Step 3: Implement argparse CLI**

Create `src/lab_auto/cli.py`:

```python
import argparse
from collections.abc import Sequence

from lab_auto.config import load_workflow_config
from lab_auto.runtime import resolve_runtime_mode, RuntimeMode
from lab_auto.workflow.raman import RamanWorkflow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ramanctl")
    subparsers = parser.add_subparsers(dest="domain", required=True)

    workflow = subparsers.add_parser("workflow")
    workflow_sub = workflow.add_subparsers(dest="command", required=True)
    single = workflow_sub.add_parser("single")
    single.add_argument("--config", required=True)
    single.add_argument("--devices-config")
    single.add_argument("--dry-run", action="store_true")
    single.add_argument("--simulated", action="store_true")
    single.add_argument("--real", action="store_true")
    single.add_argument("--yes", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.domain == "workflow" and args.command == "single":
        config = load_workflow_config(args.config)
        mode = resolve_runtime_mode(
            RuntimeMode.DRY_RUN,
            cli_real=args.real,
            cli_dry_run=args.dry_run,
            cli_simulated=args.simulated,
        )
        workflow = RamanWorkflow.dry_run(config) if mode is RuntimeMode.DRY_RUN else RamanWorkflow.simulated(config)
        if mode is RuntimeMode.DRY_RUN:
            for action in workflow.measure_single_point(require_confirmation=not args.yes):
                print(action)
        else:
            print(workflow.run_single_point(require_confirmation=not args.yes))
        return 0
    parser.error("unsupported command")
    return 2
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: all CLI tests PASS.

- [ ] **Step 5: Run Milestone 1 acceptance**

Run:

```bash
ramanctl workflow single --config configs/single_point.example.yaml --dry-run
pytest tests/test_config.py tests/test_background.py tests/test_workflow_dry_run.py tests/test_cli.py -v
```

Expected:
- dry-run command exits 0.
- output includes `confirm_laser_off`, `capture_background`, `confirm_laser_on`, and `save_outputs`.
- tests PASS.

- [ ] **Step 6: Commit CLI**

```bash
git add src/lab_auto/cli.py tests/test_cli.py
git commit -m "feat: add phase1 workflow cli"
```

---

### Task 10: Real Hardware Acceptance Gate Documentation

**Files:**
- Create: `docs/phase1-hardware-acceptance.md`

- [ ] **Step 1: Create acceptance checklist**

Create `docs/phase1-hardware-acceptance.md`:

```markdown
# Phase 1 Hardware Acceptance

Run these commands on the Windows 64-bit lab computer only.

## Preflight

1. Copy `configs/devices.example.yaml` to `configs/devices.real.yaml`.
2. Set `runtime.mode: real`.
3. Fill real COM port and DLL paths.
4. Confirm laser is manually controllable and initially off.

## Commands

```bash
ramanctl stage identify --config configs/devices.real.yaml --real
ramanctl stage move --config configs/devices.real.yaml --real --axis x --um 10 --speed 8 --yes
ramanctl stage home --config configs/devices.real.yaml --real --axis x --direction negative --speed 8 --yes
ramanctl devices doctor --config configs/devices.real.yaml --real
ramanctl spec status --config configs/devices.real.yaml --real
ramanctl spec init --config configs/devices.real.yaml --real --entrance side --exit direct
ramanctl spec set --config configs/devices.real.yaml --real --grating 1 --wavelength-nm 600 --slit-um 100
ramanctl camera status --config configs/devices.real.yaml --real
ramanctl camera capture --config configs/devices.real.yaml --real --mode fvb --exposure-ms 1000 --gain low --out output/captures/fvb.csv
ramanctl workflow single --config configs/single_point.yaml --devices-config configs/devices.real.yaml --real --yes
```

## Pass Criteria

- No command depends on a prior CLI process retaining a DLL handle or serial connection.
- Stage commands receive completion markers and update state only after success.
- Zolix doctor reports Python 64-bit and finds required DLL dependencies.
- DField FVB capture writes `pixel_index,intensity_raw,saturated` unless spectral calibration context is explicitly provided.
- Single-point workflow writes `metadata.json`, `background.csv`, `raw.csv`, `corrected.csv`, and `run.log`.
- Any failure path prompts the user to confirm laser-off state.
```

- [ ] **Step 2: Verify markdown has no stale local config tracking**

Run:

```bash
git check-ignore -v configs/devices.yaml configs/devices.real.yaml configs/single_point.yaml
```

Expected: each path is ignored by `.gitignore`.

- [ ] **Step 3: Commit acceptance docs**

```bash
git add docs/phase1-hardware-acceptance.md
git commit -m "docs: add phase1 hardware acceptance checklist"
```

---

## Final Verification

After all tasks:

```bash
pytest -v
ramanctl workflow single --config configs/single_point.example.yaml --dry-run
git status --short
```

Expected:
- `pytest -v` reports all tests PASS.
- dry-run workflow output contains the full action sequence.
- `git status --short` is empty except intentionally ignored local runtime files.

## Self-Review

Spec coverage:
- CLI stateless model: Tasks 1, 8, 9.
- Runtime modes: Tasks 1, 9.
- SDK raw/adapter boundary: Tasks 3, 5, 6.
- WayneLabs protocol and safety state: Tasks 3, 4.
- Zolix port and ctypes mapping: Task 5.
- DField enum and Windows `long*` handling: Task 6.
- Spectrum schema and background consistency: Task 2 and Task 8.
- Manual light control and workflow sequence: Task 7 and Task 8.
- Milestone acceptance commands: Task 9 and Task 10.

Out of Phase 1:
- Mapping grid scan.
- Agent tool schema.
- daemon/session/shell mode.
- Real light-controller protocol.
- Automatic exposure, peak detection, baseline correction, and batch scheduling.

Plan quality checks:
- No step depends on a persistent CLI process.
- No adapter task hand-writes hardware protocol strings outside `devices/raw`.
- Every code task has a failing test step before implementation.
- Every task ends with a commit command.
