# Phase 2 · M1 — Real PWM Light Backend (Modbus RTU) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status (2026-06-13): Code-complete, pending on-hardware acceptance.** This
> first Phase 2 milestone was developed and tested entirely with a simulated
> in-memory transport on macOS; the real serial run remains deferred to the
> shared on-hardware acceptance pass, exactly like Phase 1.

**Goal:** Add a real PWM light-source backend (`type: pwm_modbus`) that speaks Modbus
RTU to the multi-channel PWM signal generator, with all safety interlocks from the
spec, while keeping the existing `manual` backend and the stateless-CLI / `raw -> adapter`
boundary intact.

**Architecture:** Modbus frame bytes, CRC16, register numbers, and function codes live
ONLY in a new `raw/pwm_modbus.py`. The adapter (`PwmModbusLight` in `devices/light.py`)
exposes the same typed light interface the workflow already calls
(`require_off_confirmation`, `require_on_confirmation`, `confirm_laser_off`,
`confirm_laser_on`, `get_state`) plus `led_on`/`led_off`, and performs the
read-back-confirmed safety sequence. Config and factory dispatch on `light.type`.

**Tech Stack:** Python 3.11+, standard library, `PyYAML`, `pyserial` (real transport
only), `pytest`. No new third-party Modbus library — the RTU framing is small and
must stay auditable inside `raw/`.

---

## Source Requirements

Primary spec: [`docs/superpowers/specs/2026-06-04-lab-automation-platform-design.md`](../specs/2026-06-04-lab-automation-platform-design.md)
- §6.5 PWM controller protocol & register map
- §12.2 light-source state machine
- §12.3 Phase 2 PWM safety constraints
- §10 config shape (commented `pwm_modbus` block)

Scope reference: [`docs/superpowers/plans/2026-06-09-lab-automation-phase2-scope.md`](2026-06-09-lab-automation-phase2-scope.md) §3

Repository constraints: [`AGENTS.md`](../../../AGENTS.md)

Existing patterns to mirror (do not break):
- Raw layer: `src/lab_auto/devices/raw/waynelabs_protocol.py` (module functions + thin class, `ProtocolError(ValueError)`, frozen dataclasses, no I/O).
- Config: `src/lab_auto/config.py` (`_finite_int` / `_finite_float` / `_as_bool`, frozen dataclasses, `KeyError -> ConfigError`).
- Adapter transport injection + dry-run: `src/lab_auto/devices/waynelabs_stage.py` (`transport`, deadline read loop, `DeviceError`).
- Manual light interface the workflow consumes: `src/lab_auto/devices/light.py` (`ManualLight`).
- Factory dispatch: `src/lab_auto/devices/factory.py` (`create_light`).

## File Map

```text
src/lab_auto/devices/raw/pwm_modbus.py     # CREATE: CRC16, frame build/parse, register map helpers
src/lab_auto/devices/light_safety.py       # CREATE: pure config/state validation for the PWM backend
src/lab_auto/devices/light.py              # MODIFY: add PwmModbusLight alongside ManualLight
src/lab_auto/config.py                     # MODIFY: extend LightConfig (+ PwmChannel) and loader
src/lab_auto/devices/factory.py            # MODIFY: create_light dispatch on light.type
configs/devices.example.yaml               # MODIFY: keep manual default; document pwm block (already commented)
docs/phase2-hardware-acceptance.md         # CREATE: deferred real-serial acceptance checklist
tests/test_pwm_modbus_protocol.py          # CREATE
tests/test_light_config.py                 # CREATE
tests/test_pwm_light_adapter.py            # CREATE
tests/test_hardware_cli.py                 # MODIFY (only if real-mode light dispatch needs a wiring test)
```

## Execution Rules

- Every code task starts with a failing test step, then a run-to-confirm-red step, then implementation, then run-to-green, then a commit.
- Never import `serial` in tests; inject a fake transport.
- The raw module performs NO I/O and NO `time`/`serial` import. It only builds and parses `bytes`.
- All voltages are deci-volt integers on the wire. 5.0 V is decimal `50` = register word `0x0032` = cable bytes `00 32`. Never use `0x0050`.
- `station_id == 0` is rejected for all normal read/write. Address-change and `Reg23`/`Reg24`/`Reg25` writes are out of scope for this milestone — do not implement them.

---

## Register & Constant Reference (encode into `raw/pwm_modbus.py`)

| Register(s) | Meaning | Encoding |
|---|---|---|
| `Reg0` | reserved, read-only | never write |
| `Reg1` | global output voltage | unit 0.1 V; hard max 5.0 V (`50`/`0x0032`) |
| `Reg2-Reg11` | CH1–CH5 frequency | per channel hi<<16 \| lo, 32-bit Hz |
| `Reg12-Reg16` | CH1–CH5 duty | unit 0.1 % |
| `Reg17-Reg21` | CH1–CH5 output state | `0`=off `1`=on |
| `Reg22` | current display channel | read context only |
| `Reg23`/`Reg24`/`Reg25` | key-lock / baud / undefined | **forbidden to write** |

Function codes: `0x03` read holding, `0x06` write single, `0x10` write multiple.
Channel→register helpers: `freq_registers(ch) -> (hi_addr, lo_addr)`, `duty_register(ch) -> addr`, `output_state_register(ch) -> addr`, `VOLTAGE_REGISTER = 1`.

CRC16 (Modbus): poly `0xA001`, init `0xFFFF`, appended little-endian (low byte first).
Canonical test vector: request `01 03 00 00 00 01` → CRC bytes `84 0A`.

---

## Task 1: PWM Modbus Raw Protocol

**Files:** Create `src/lab_auto/devices/raw/pwm_modbus.py`, `tests/test_pwm_modbus_protocol.py`.

- [x] **Step 1: Write raw protocol tests**

Create `tests/test_pwm_modbus_protocol.py` covering pure framing only (no I/O):

- `crc16(b"\x01\x03\x00\x00\x00\x01") == b"\x84\x0a"` (canonical vector).
- `build_read_request(station=1, address=1, count=1)` returns `01 03 00 01 00 01` + correct CRC.
- `build_write_single_request(station=1, address=17, value=1)` returns `01 06 00 11 00 01` + CRC.
- `build_write_multiple_request(station=1, address=2, values=[0x0000, 0x03E8])` returns `01 10 00 02 00 02 04 00 00 03 E8` + CRC.
- `build_read_request(station=0, ...)` raises `ProtocolError` (station 0 forbidden).
- Writing `VOLTAGE_REGISTER` with value > 50 via a `build_write_voltage_request` helper raises `ProtocolError` (5.0 V hard cap enforced at the frame layer too).
- `parse_read_response` on a well-formed `0x03` reply returns the list of register words.
- `parse_read_response` rejects: bad CRC, station mismatch, function-code mismatch, Modbus exception reply (`func | 0x80`), byte-count not equal to `2 * requested_count`.
- `parse_write_ack` validates the echo for `0x06` and the start/quantity for `0x10`, and rejects exception replies and bad CRC.
- Register/channel helpers: `output_state_register(2) == 18`, `duty_register(1) == 12`, `freq_registers(1) == (2, 3)`, and out-of-range channel (`<1` or `>5`) raises `ProtocolError`.
- Voltage codec: `voltage_to_register(5.0) == 50`, `voltage_to_register(5.1)` raises, `register_to_voltage(50) == 5.0`.

- [x] **Step 2: Run tests to verify the raw module is missing**

```bash
.venv/bin/python -m pytest tests/test_pwm_modbus_protocol.py -q
```

Expected: collection/import error or failures (module absent).

- [x] **Step 3: Implement `raw/pwm_modbus.py`**

Mirror `waynelabs_protocol.py` structure: module-level pure functions + a thin
`PwmModbusProtocol` class wrapper; reuse the existing `ProtocolError(ValueError)`
convention (define a local `ProtocolError(ValueError)` in this module to keep raw
modules self-contained, consistent with `waynelabs_protocol.py`).

Implement:
- `crc16(payload: bytes) -> bytes` (2 bytes, low-first).
- Frame builders: `build_read_request`, `build_write_single_request`, `build_write_multiple_request`, `build_write_voltage_request` (enforces ≤ `0x0032`).
- Parsers: `parse_read_response(frame, *, station, function, count) -> list[int]`, `parse_write_ack(frame, *, station, function, address, ...) -> None`. Both must validate CRC, station equals the requested non-zero station, function code matches and is not an exception (`& 0x80`), and length/byte-count is consistent.
- Constants: `READ=0x03`, `WRITE_SINGLE=0x06`, `WRITE_MULTIPLE=0x10`, `VOLTAGE_REGISTER=1`, `MAX_VOLTAGE_DECIVOLT=50`, `FORBIDDEN_REGISTERS={23,24,25}`.
- Channel/register helpers and the voltage codec listed above.
- `expected_read_response_len(count) -> int` (= `5 + 2*count`) and `EXCEPTION_RESPONSE_LEN = 5`, so the adapter can read deterministic byte counts.

No `serial`, no `time`, no global voltage write helper that bypasses the cap.

- [x] **Step 4: Run raw tests**

```bash
.venv/bin/python -m pytest tests/test_pwm_modbus_protocol.py -q
```

Expected: all pass.

- [x] **Step 5: Commit raw protocol**

```bash
git add src/lab_auto/devices/raw/pwm_modbus.py tests/test_pwm_modbus_protocol.py
git commit -m "feat(light): add pwm modbus rtu raw protocol"
```

---

## Task 2: Light Config Extension and Validation

**Files:** Modify `src/lab_auto/config.py`; create `src/lab_auto/devices/light_safety.py`; create `tests/test_light_config.py`.

- [x] **Step 1: Write light-config tests**

Create `tests/test_light_config.py`:

- A `manual` light config still loads (backward compatible: only `type` + `manual_light_control`).
- A `pwm_modbus` config loads into `LightConfig` with `port`, `station_id`, `baudrate`, `max_output_voltage_v`, `required_output_voltage_v`, and a `channels` mapping of `{led, laser}` → `PwmChannel(channel, frequency_hz, duty_percent, default_off_required)`.
- Rejections (each raises `ConfigError`): unknown `type`; `station_id == 0`; `max_output_voltage_v > 5.0`; `required_output_voltage_v > max_output_voltage_v`; missing `channels.laser`; channel index outside 1–5; duplicate channel index across led/laser; negative/zero `frequency_hz`; `duty_percent` outside 0–100.
- `manual_light_control` must be `false` when `type == pwm_modbus` (auto-mode backends cannot also claim manual control) → `ConfigError` otherwise.

- [x] **Step 2: Run tests to verify the new fields are missing**

```bash
.venv/bin/python -m pytest tests/test_light_config.py -q
```

Expected: failures (fields/validation absent).

- [x] **Step 3: Implement config extension and `light_safety.py`**

In `config.py`:
- Add a frozen `PwmChannel` dataclass: `channel: int`, `frequency_hz: int`, `duty_percent: float`, `default_off_required: bool`.
- Extend `LightConfig` with optional PWM fields, defaulting to `None` so `manual` configs are unchanged: `port`, `station_id`, `baudrate`, `max_output_voltage_v`, `required_output_voltage_v`, `channels: dict[str, PwmChannel] | None`.
- In `load_devices_config`, branch on `light["type"]`: `manual` keeps current behavior; `pwm_modbus` parses the new fields with `_finite_int` / `_finite_float` / `_as_bool`.

Put all cross-field rules in a new pure `src/lab_auto/devices/light_safety.py`
(mirrors `optics_validation.py`): `validate_pwm_light_config(cfg) -> None` raising
`ConfigError`. Keep the raw 5.0 V constant defined in `raw/pwm_modbus.py` and import
it here, so there is a single source of truth.

- [x] **Step 4: Run light-config tests**

```bash
.venv/bin/python -m pytest tests/test_light_config.py tests/test_config.py -q
```

Expected: new tests pass; existing config tests still pass.

- [x] **Step 5: Commit config extension**

```bash
git add src/lab_auto/config.py src/lab_auto/devices/light_safety.py tests/test_light_config.py
git commit -m "feat(light): extend LightConfig for pwm modbus backend"
```

---

## Task 3: PwmModbusLight Adapter and Safety Sequence

**Files:** Modify `src/lab_auto/devices/light.py`; create `tests/test_pwm_light_adapter.py`.

- [x] **Step 1: Write adapter safety tests (fake transport)**

Create `tests/test_pwm_light_adapter.py` with an in-memory `FakeModbusTransport`
that records written request frames and returns scripted response frames (built with
`raw/pwm_modbus.py` helpers, so tests stay protocol-accurate). Cover:

- **Interface parity:** `PwmModbusLight` exposes `require_off_confirmation()` / `require_on_confirmation()` (returning the non-manual `"laser_off"` / `"laser_on"` action strings), `confirm_laser_off(require_confirmation=...)`, `confirm_laser_on(require_confirmation=...)`, and `get_state()` — so `RamanWorkflow` drives it unchanged.
- **`laser_on()` happy path** performs, in order: read `Reg1` == `0x0032`; read `Reg17-21` and confirm non-target channels are `0`; read target-channel freq/duty and confirm they match config; write target output-state register; read back that register == `1`; only then set `laser_state="on_confirmed"`.
- **Refuse-on-readback-failure:** if the post-write read-back of the target state is not `1`, `laser_on()` raises `DeviceError` and `laser_state` is NOT `on_confirmed`.
- **Voltage gate:** if `Reg1` read-back ≠ `0x0032`, `laser_on()` refuses (and never writes a value > 50; any attempt is blocked at the raw layer).
- **`Reg1` write precondition:** before any write to `Reg1`, the adapter reads `Reg17-21` and requires all `0`; if any channel is on it refuses (no direct `Reg1` modification).
- **LED isolation:** `led_on()` sets `led_state="on_confirmed"` only, never touches `laser_state`, and does NOT satisfy the laser precondition (a follow-up `acquire`-style check still sees `laser_state != on_confirmed`).
- **Off / failure path:** `laser_off()` / `led_off()` best-effort write all configured channels off and read back `0`; on read-back failure they surface a state requiring manual confirmation rather than silently claiming off.
- **Forbidden writes:** the adapter never emits writes to `Reg23/24/25` and never issues a station-0 frame (assert by inspecting recorded frames).
- **Read-back validity:** a response with bad CRC / wrong station / exception code causes the operation to raise `DeviceError` (delegated to the raw parser).
- **Dry-run:** constructing with `dry_run=True` performs no transport I/O and returns deterministic planned actions / states.

- [x] **Step 2: Run adapter tests to verify the class is missing**

```bash
.venv/bin/python -m pytest tests/test_pwm_light_adapter.py -q
```

Expected: failures (class absent).

- [x] **Step 3: Implement `PwmModbusLight`**

Add `PwmModbusLight` to `devices/light.py` next to `ManualLight`. Inject
`transport` (with `write(bytes)` and a deadline-based `read(n) -> bytes`, mirroring
`WaynelabsStage`) plus the parsed `LightConfig`. Use only `raw/pwm_modbus.py` for
framing/parsing and `DeviceError` for failures. Track independent `laser_state` and
`led_state` strings matching spec §12.2 (`unknown` / `manual_wait` / `off_confirmed`
/ `on_confirmed`). Implement the full read-back-confirmed sequence from
Task 3 Step 1. Honor `dry_run`. Add per-operation timeouts as module constants
(e.g. `PWM_MODBUS_READ_TIMEOUT_S`), consistent with the WayneLabs timeout style.

`require_off_confirmation()` / `require_on_confirmation()` return the real action
strings (`"laser_off"` / `"laser_on"`); `confirm_laser_off()` / `confirm_laser_on()`
actually drive `laser_off()` / `laser_on()` and set state only after read-back.

- [x] **Step 4: Run adapter tests**

```bash
.venv/bin/python -m pytest tests/test_pwm_light_adapter.py -q
```

Expected: all pass.

- [x] **Step 5: Commit adapter**

```bash
git add src/lab_auto/devices/light.py tests/test_pwm_light_adapter.py
git commit -m "feat(light): add read-back-confirmed pwm modbus light adapter"
```

---

## Task 4: Factory Dispatch on light.type

**Files:** Modify `src/lab_auto/devices/factory.py`; modify `tests/test_hardware_cli.py` (or add a focused factory test).

- [x] **Step 1: Write factory dispatch test**

Add a test that `DeviceFactory.create_light`:
- returns `ManualLight` for `type: manual` with `manual_light_control: true` (unchanged);
- still raises `DeviceError` for `type: manual` with `manual_light_control: false` (unchanged Phase 1 contract);
- for `type: pwm_modbus`, opens the configured serial port via an injected/patched transport factory and returns a `PwmModbusLight` (assert type and that the configured `station_id` / `channels` reached the adapter). Patch the serial open so no real port is touched.

- [x] **Step 2: Run to verify dispatch is missing**

```bash
.venv/bin/python -m pytest tests/test_hardware_cli.py -q
```

Expected: the new pwm dispatch test fails.

- [x] **Step 3: Implement dispatch**

In `create_light`, branch on `devices_config.light.type`:
- `manual` → existing behavior.
- `pwm_modbus` → call `validate_pwm_light_config`, open `serial.Serial(port, baudrate, timeout=...)` exactly as `create_stage` does (wrap failures in `DeviceError`), and return `PwmModbusLight(devices_config.light, transport=..., dry_run=False)`.
- unknown → `DeviceError`.

Keep the serial import local to the method (matches `create_stage`). Ensure
`create_single_point_workflow`'s `finally` close path also closes the light when it
owns a real transport.

- [x] **Step 4: Run hardware CLI tests**

```bash
.venv/bin/python -m pytest tests/test_hardware_cli.py tests/test_real_workflow_cli.py -q
```

Expected: all pass.

- [x] **Step 5: Commit factory dispatch**

```bash
git add src/lab_auto/devices/factory.py tests/test_hardware_cli.py
git commit -m "feat(light): dispatch real light backend on light.type"
```

---

## Task 5: Deferred Hardware Acceptance Doc and Full Verification

**Files:** Create `docs/phase2-hardware-acceptance.md`; touch `configs/devices.example.yaml` only if the commented pwm block needs to match the final field names.

- [x] **Step 1: Create `docs/phase2-hardware-acceptance.md`**

Real-serial checklist (run on the Windows lab computer only), covering:
- Preflight: confirm channel mapping (which channel is laser vs LED), COM port, non-zero station id, frequency/duty per channel, wiring safety of the regulated-supply output, laser initially off and manually controllable.
- Commands: `ramanctl` light status/doctor against `configs/devices.real.yaml` with `type: pwm_modbus`, then a single-point workflow with `--real --yes`.
- Pass criteria (from spec §6.5 / §12.2 / §12.3): `Reg1` read back as `0x0032`; non-target channels confirmed off before opening any channel; target freq/duty match config; output state read back as `1` after laser-on and `0` after laser-off and on failure; no writes to `Reg23/24/25`; no station-0 frames; LED-on never satisfies the laser precondition; any failure prompts manual laser-off confirmation.

- [x] **Step 2: Verify example config field names match the implementation**

Ensure the commented `pwm_modbus` block in `configs/devices.example.yaml` uses the
exact field names parsed by `load_devices_config`. Keep the default `type: manual`.

- [x] **Step 3: Full suite + dry-run regression**

```bash
.venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python -m lab_auto workflow single --config configs/single_point.example.yaml --dry-run
```

Expected: all tests pass (Phase 1 + new M1 tests); the dry-run workflow still emits
the full single-point action sequence unchanged (manual light path is the default).

- [x] **Step 4: Commit acceptance docs**

```bash
git add docs/phase2-hardware-acceptance.md configs/devices.example.yaml
git commit -m "docs(light): add phase2 m1 pwm hardware acceptance checklist"
```

---

## Final Verification

```bash
.venv/bin/python -m pytest -q
git status --short
```

Expected: all tests pass; working tree clean except intentionally ignored runtime files.

## Self-Review

Spec coverage:
- Modbus RTU framing, CRC, function codes, register map: Task 1 (§6.5).
- 5.0 V hard cap as `0x0032`, station-0 rejection, forbidden registers: Task 1 + Task 2 (§6.5, §12.3).
- Read-back-confirmed `laser_on` / `led_on`, LED isolation, off/failure best-effort: Task 3 (§12.2, §12.3).
- Manual backend untouched, dry-run preserved, stateless CLI intact: Task 3 + Task 4 + Task 5.
- Config validation and single source of truth for the voltage cap: Task 2.

Out of M1 scope (later milestones / on-hardware):
- Address-change command and `Reg23/24/25` writes (maintenance-only; not implemented).
- HTTP light backend (M6).
- Real serial run and channel-mapping confirmation (deferred acceptance, §16.1).
- `set_intensity_percent` (only if later confirmed; must map to per-channel freq/duty, never `Reg1`).

Plan quality checks:
- No step depends on a persistent CLI process or a real serial port.
- No adapter/workflow/CLI code hand-writes Modbus bytes outside `raw/pwm_modbus.py`.
- Every code task has a failing test step before implementation and ends with a commit.
- The 5.0 V cap is enforced at the raw layer AND validated at config load.
