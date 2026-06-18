# Phase 2 · M2 — Tray → Wafer → Sample Layered Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

---

## RESUME / CURRENT STATE (read this first after any context compression)

- **M1 (PWM Modbus light backend) is DONE and merged to `main`** — raw protocol, `LightConfig` extension, `PwmModbusLight` adapter with read-back interlocks, factory dispatch, review fixes. Suite was **295 tests passing** before M2.
- **M2 (this plan) is DONE and merged to `main`** — all 9 tasks implemented TDD, one commit each. Suite **347 tests passing**. New modules: `vision/mask_centers.py`, `vision/calibration.py`, `scan/tray.py`, `scan/pattern.py`, `processing/burn_check.py`, `workflow/tray_scan.py`; config dataclasses + loader, CLI `ramanctl scan tray`, and factory `create_tray_scan_workflow` wired. Real calibration data collection, real CCD imaging/recognition hook, and per-objective calibration values are deferred to the shared on-hardware pass (`docs/phase2-hardware-acceptance.md` M2 section), like Phase 1/M1.
- Run tests with: `PYTHONPATH=src .venv/bin/python -m pytest -q`. Dry-run a workflow with `PYTHONPATH=src .venv/bin/python -m lab_auto ...`.
- The package is NOT pip-installed; always use `PYTHONPATH=src`.
- Confirmed design decisions and their rationale live in **§ Confirmed Decisions** below and in the scope plan `docs/superpowers/plans/2026-06-09-lab-automation-phase2-scope.md` §4 (M2).

---

## Goal

Automate the real lab workflow: a **sample tray** holds a grid of cells, **one wafer per cell**, **several samples per wafer**. For each wafer, move to its center, image the whole wafer, get a recognition **mask**, extract **sample centers** from the mask, and measure each center plus 2 surrounding points (each single-point Raman ×2 for a burn check), returning to the wafer center between samples.

## Architecture & boundaries (do not break)

- Reuse the existing `raw -> adapter -> workflow -> CLI` layering. M2 adds **pure-logic modules** (vision, geometry, scan pattern, burn check) + one **orchestration workflow** + CLI wiring. No module above `devices/raw/*` hand-writes hardware protocol.
- Every hardware action must be dry-run-able and unit-tested with injected fakes. No `serial`/`ctypes`/`numpy` import in pure modules or tests.
- Reuse the existing **single-point workflow** (`src/lab_auto/workflow/raman.py`, `RamanWorkflow`) as the per-point measurement primitive, and the existing **stage safety state machine** (`src/lab_auto/devices/waynelabs_stage.py`: `AxisState`, soft limits, `PositionLedger`).
- **No new hard dependency.** Connected-components on the mask is implemented in pure stdlib (BFS/union-find) so M2 stays dependency-free and testable. `numpy` is only a *possible future optimization* for large real CCD images — do NOT add it now; if real performance ever needs it, that's a separate decision.

## Confirmed Decisions (from advisor/engineer, 2026-06-18)

1. **Not the instrument's raster mapping.** It's discrete sample-center scanning (spec §4.4), not MAPS Sample Stage Mapping (SOP §5).
2. **冯博士 provides only the recognized image / mask. WE extract the centers** (connected components → centroid). Mask exact form (binary / labeled / boxed) still to confirm — develop against a binary/labeled 2D grid; a thin image→grid loader is the only hardware-side piece (deferred).
3. **Per detected center: 3 spatial points** = center + 2 **parameterized** surrounding points. **Each point's single-point Raman is done twice** = 6 acquisitions/center.
4. **The two acquisitions are a BURN CHECK**, not an average: compare them; deviation over threshold ⇒ flag burn/anomaly in the manifest. Keep both spectra.
5. **Image center = coordinate origin** (it equals the stage position at capture). A sample center at pixel `p` maps to a **relative stage move** via a per-objective **affine** calibration. Measurement point is assumed to be the image center (= laser spot) — to confirm on hardware.
6. **Recognition gives pixel coords; M2 does the pixel→stage calibration.**
7. **Wafer centers come from known tray geometry** (rows/cols/pitch/first-cell offset/order), not per-wafer detection.
8. **Return to wafer center after each sample** (every sample move is referenced to the wafer-center origin → bounds accumulated error).
9. Laser **on/off = PWM** (M1, done); laser **power = half-wave plate** (separate software module, interface pending) — NOT part of M2; M2 uses M1's existing `laser_on/off` via the single-point workflow.

## Source references

- Scope: `docs/superpowers/plans/2026-06-09-lab-automation-phase2-scope.md` §4 (M2), §5 (open questions).
- Spec: `docs/superpowers/specs/2026-06-04-lab-automation-platform-design.md` §4.4 (sample id), §12.1 (stage state machine — Mapping requires X/Y homed/user_zeroed), §17 (interruptible/resumable/auditable).
- Lab SOP: `docs/lab-sop-pl-mapping-zolix-ocr.md`.
- Patterns to mirror: `config.py` (`_finite_int/_finite_float/_as_bool`, frozen dataclasses, `KeyError→ConfigError`), `workflow/raman.py` (dry-run `plan()` returning an action-string list; `RamanWorkflow.real(...)` constructor), `devices/waynelabs_stage.py` (soft limits, `AxisState`, ledger), `processing/background.py` (pure spectrum math), `cli.py` (argparse subcommands, `--dry-run`/`--real`/`--config`), `devices/factory.py` (real wiring + finally-close).

## Open inputs (do NOT block development — use placeholders/fixtures)

- Mask exact form → develop against a 2D `list[list[int]]` (0=bg). 
- Tray geometry numbers, per-objective calibration values, surrounding-point default distance/angles, burn-check metric/threshold → put sane defaults in the example config; real values set on hardware.
- Whether measurement point exactly equals image center → assumed; if not, calibration gains a separate laser-spot pixel (additive, not structural).

## File map

```text
src/lab_auto/vision/__init__.py             # CREATE
src/lab_auto/vision/mask_centers.py         # CREATE: mask -> sample centers (pure connected-components + centroid)
src/lab_auto/vision/calibration.py          # CREATE: affine pixel->stage fit + apply (pure)
src/lab_auto/scan/__init__.py               # CREATE
src/lab_auto/scan/tray.py                   # CREATE: tray geometry -> wafer-center stage coords (pure)
src/lab_auto/scan/pattern.py                # CREATE: center + surrounding measurement points (pure)
src/lab_auto/processing/burn_check.py       # CREATE: compare two spectra -> deviation + burned flag (pure)
src/lab_auto/workflow/tray_scan.py          # CREATE: orchestration (dry-run + fake-adapter), manifest, safety, resume
src/lab_auto/config.py                      # MODIFY: + Calibration, TrayLayout, ScanPattern, TrayScanConfig + loader
src/lab_auto/cli.py                         # MODIFY: + `scan` command group
src/lab_auto/devices/factory.py             # MODIFY: + create_tray_scan_workflow (real wiring)
configs/tray_scan.example.yaml              # CREATE: example scan config
docs/phase2-hardware-acceptance.md          # MODIFY: add M2 (tray scan) deferred acceptance section
tests/test_mask_centers.py                  # CREATE
tests/test_calibration.py                   # CREATE
tests/test_tray_geometry.py                 # CREATE
tests/test_scan_pattern.py                  # CREATE
tests/test_burn_check.py                    # CREATE
tests/test_tray_scan_config.py              # CREATE
tests/test_tray_scan_workflow.py            # CREATE
tests/test_scan_cli.py                      # CREATE
```

## Execution rules

- Every code task: failing test first → run-to-confirm-red → implement → run-to-green → commit.
- Pure modules: no `serial`/`ctypes`/`numpy`/`time`/`random` import. Deterministic.
- Reuse `ConfigError`/`DeviceError`/`SafetyError` from `lab_auto.errors`.
- Stage: M2 must refuse to scan unless X and Y are `homed` or `user_zeroed` (spec §12.1); every target point must pass the existing soft-limit check; out-of-range points are skipped or abort per config (`on_out_of_range: skip|abort`).

---

## Coordinate & calibration math (implement exactly as written)

Convention (all in home-relative stage micrometers and image pixels):

- Image captured at the wafer center; the stage is then at `wafer_center` (home-relative um). The image-center pixel is `c = (cx, cy)`.
- A detected sample center is at pixel `p = (px, py)`.
- We want the sample (imaged at `p`) to end up at the measurement point = image center `c` (= laser spot). The image feature must shift by `(c - p)` pixels.
- Empirically, a stage move `S` (um) shifts the imaged feature by `P` (pixels): `P = B · S` (B = pixels-per-um, 2×2). Therefore the stage move that produces image shift `(c - p)` is `S = A · (c - p)` where **`A = B⁻¹` (um-per-pixel, 2×2)**.

So:
- **Apply:** `pixel_to_stage_delta(A, image_center, pixel) = A @ (image_center - pixel)` → returns `(dx_um, dy_um)`, the relative move from the wafer center to put that sample under the laser.
- **Fit:** from calibration samples `{(S_i, P_i)}` (commanded stage move `S_i` um, observed feature pixel shift `P_i`): fit `B` by least squares `B = (Σ P_iS_iᵀ)(Σ S_iS_iᵀ)⁻¹`, then `A = B⁻¹`. Need ≥2 linearly-independent `S_i` (e.g., `(D,0)` and `(0,D)`). 2×2 inverse/solve in pure Python.

`A` captures scale, rotation, anisotropy, and axis sign all at once. Store `A` + `image_center` + `objective` per objective.

---

## Task 1: Mask → sample centers (pure)

**Files:** `src/lab_auto/vision/__init__.py`, `src/lab_auto/vision/mask_centers.py`, `tests/test_mask_centers.py`.

- [x] **Step 1: Write tests.** Cover:
  - `extract_centers(mask, *, min_area=1)` on a 2D `list[list[int]]` (0=background, nonzero=foreground) returns a list of `SampleCenter(pixel_x, pixel_y, area, label)` where `pixel_x/pixel_y` are the **centroid** (mean column/row, float), one per 4-connected foreground component.
  - A single rectangular blob → one center at its geometric centroid.
  - Two separated blobs → two centers; diagonal-only touching blobs stay separate (4-connectivity).
  - `min_area` filters out tiny blobs (noise).
  - Deterministic ordering (e.g., by `(round(pixel_y), round(pixel_x))`).
  - Empty/all-zero mask → `[]`. Ragged rows → `ConfigError`/`ValueError`.
- [x] **Step 2: Run to confirm red.** `PYTHONPATH=src .venv/bin/python -m pytest tests/test_mask_centers.py -q`
- [x] **Step 3: Implement.** `SampleCenter` frozen dataclass; `extract_centers` via pure-stdlib 4-connected components (iterative BFS/stack or union-find), centroid = mean of member pixel coords, `area` = pixel count, stable label ids, deterministic sort. No numpy.
- [x] **Step 4: Run green.**
- [x] **Step 5: Commit** `feat(vision): extract sample centers from recognition mask`.

## Task 2: Pixel→stage affine calibration (pure) + Calibration config

**Files:** `src/lab_auto/vision/calibration.py`, `src/lab_auto/config.py` (add `Calibration`), `tests/test_calibration.py`.

- [x] **Step 1: Write tests.**
  - `fit_affine(samples)` where `samples=[(stage_delta_um, pixel_delta), ...]`: pick a known `A` (e.g. scale 0.5 um/px + small rotation), synthesize `P_i = A⁻¹ · S_i` for non-colinear `S_i`, assert the fitted `A` recovers it (within tolerance).
  - Fewer than 2 independent samples → `ConfigError`.
  - `pixel_to_stage_delta(calib, pixel)` returns `A @ (image_center - pixel)`; a pixel at the image center → `(0,0)`.
  - 2×2 inverse helper handles a singular matrix → `ConfigError`.
- [x] **Step 2: Run red.**
- [x] **Step 3: Implement.** Pure 2×2 linear algebra (matmul, inverse, least-squares via normal equations). `Calibration` frozen dataclass: `objective: str`, `a11,a12,a21,a22` (the `A` matrix), `image_center_px`, `image_center_py`. Add parsing to `config.py` (mirror existing helpers).
- [x] **Step 4: Run green.**
- [x] **Step 5: Commit** `feat(vision): affine pixel-to-stage calibration fit and apply`.

## Task 3: Tray geometry (pure) + TrayLayout config

**Files:** `src/lab_auto/scan/__init__.py`, `src/lab_auto/scan/tray.py`, `src/lab_auto/config.py` (add `TrayLayout`), `tests/test_tray_geometry.py`.

- [x] **Step 1: Write tests.**
  - `wafer_centers(layout)` returns wafer-center **home-relative stage coords** `(x_um, y_um, row, col, index)` for an `rows×cols` grid: `x = first_cell_offset.x + col*pitch.x`, `y = first_cell_offset.y + row*pitch.y`.
  - `order="row_major"` vs `"serpentine"` produce the expected visiting sequence (serpentine reverses column direction on alternate rows).
  - Validation: positive rows/cols, positive pitch → else `ConfigError`.
- [x] **Step 2: Run red.**
- [x] **Step 3: Implement.** `TrayLayout` frozen dataclass (`rows, cols, pitch_um{x,y}, first_cell_offset_um{x,y}, order`); pure `wafer_centers`. Add config parsing.
- [x] **Step 4: Run green.**
- [x] **Step 5: Commit** `feat(scan): tray geometry to wafer-center coordinates`.

## Task 4: Scan pattern points (pure) + ScanPattern config

**Files:** `src/lab_auto/scan/pattern.py`, `src/lab_auto/config.py` (add `ScanPattern`), `tests/test_scan_pattern.py`.

- [x] **Step 1: Write tests.**
  - `measurement_points(center_xy_um, pattern)` returns ordered points `[(x,y,role)]`: first the `center` (role `"center"`), then `surrounding.count` points at `surrounding.distance_um` and `surrounding.angles_deg` from the center (role `"surrounding_0"`, `...`). Default `count=2`.
  - Geometry: a point at distance D angle θ = `center + (D·cosθ, D·sinθ)`; verify exact coords for angles like 0/90/180.
  - `repeats_per_point` and `burn_check{metric, threshold}` are carried on the pattern for the workflow to read.
  - Validation: `count` matches `len(angles_deg)`, positive distance, `repeats_per_point >= 2` → else `ConfigError`.
- [x] **Step 2: Run red.**
- [x] **Step 3: Implement.** `ScanPattern` frozen dataclass (`repeats_per_point`, `burn_metric`, `burn_threshold`, `surrounding_count`, `surrounding_distance_um`, `surrounding_angles_deg: list[float]`); pure `measurement_points`. Add config parsing.
- [x] **Step 4: Run green.**
- [x] **Step 5: Commit** `feat(scan): per-center measurement point pattern`.

## Task 5: Burn check (pure)

**Files:** `src/lab_auto/processing/burn_check.py`, `tests/test_burn_check.py`.

- [x] **Step 1: Write tests.**
  - `compare_spectra(a, b, *, metric, threshold)` returns `{deviation: float, burned: bool}`.
  - `metric="relative_l2"`: deviation = `||a-b|| / (||a||+eps)`; identical spectra → 0, not burned; a large change → over threshold → `burned=True`.
  - Length mismatch → `ValueError`.
  - Deterministic; reuse the spectrum representation from `workflow/data.py` / `processing/background.py` (lists of intensities aligned by pixel/wavelength).
- [x] **Step 2: Run red.**
- [x] **Step 3: Implement.** Pure; support at least `relative_l2` (extensible by metric name).
- [x] **Step 4: Run green.**
- [x] **Step 5: Commit** `feat(processing): burn-check comparison of repeated spectra`.

## Task 6: TrayScanConfig loader + example config

**Files:** `src/lab_auto/config.py` (add `TrayScanConfig` + `load_tray_scan_config`), `configs/tray_scan.example.yaml`, `tests/test_tray_scan_config.py`.

- [x] **Step 1: Write tests.** Load `configs/tray_scan.example.yaml` into `TrayScanConfig` containing: `devices_config` path, `sample` info, `optics`+`acquisition` (reuse single-point shapes for the per-point measurement), `tray` (`TrayLayout`), `pattern` (`ScanPattern`), `calibration` (`Calibration`), `output`, and `on_out_of_range: skip|abort`. Reject malformed/unknown values with `ConfigError`. Reuse `load_workflow_and_devices`-style devices merge.
- [x] **Step 2: Run red.**
- [x] **Step 3: Implement.** `TrayScanConfig` frozen dataclass + loader composing the dataclasses from Tasks 2–4 and the existing `OpticsConfig`/`AcquisitionConfig`/`OutputConfig`. Create `configs/tray_scan.example.yaml` with sane placeholder values (documented as "set on hardware").
- [x] **Step 4: Run green** (also run `tests/test_config.py` to confirm no regressions).
- [x] **Step 5: Commit** `feat(config): tray-scan configuration loader and example`.

## Task 7: Tray scan workflow orchestration

**Files:** `src/lab_auto/workflow/tray_scan.py`, `tests/test_tray_scan_workflow.py`.

The orchestration consumes injected devices (stage, spectrometer, camera, light) + a **mask provider** (in dry-run/tests, a fixture returning a mask per wafer; on hardware, capture → recognition). Reuse `RamanWorkflow` for the per-point measurement.

Algorithm:
```
refuse unless stage X and Y are homed/user_zeroed         # spec §12.1
for wafer in wafer_centers(tray):                          # ordered
    move stage to wafer_center (home-relative)             # via ledger-relative move
    mask = mask_provider(wafer)                            # capture+recognize on hw; fixture in tests
    centers = extract_centers(mask, min_area=...)
    for center in centers:
        delta = pixel_to_stage_delta(calib, center.pixel)  # relative to wafer center
        sample_xy = wafer_center + delta
        for (x, y, role) in measurement_points(sample_xy, pattern):
            if not within soft limits: skip-or-abort (per on_out_of_range)
            move stage to (x, y)
            spectra = [measure_single_point() for _ in range(pattern.repeats_per_point)]   # ×2
            burn = compare_spectra(spectra[0], spectra[1], ...)
            record point result (coords, role, burn) + save outputs
        move stage back to wafer_center                    # return after each sample (decision 8)
write manifest (wafer -> sample center -> points; pixel+stage coords, burn flags, status, paths)
```

- [x] **Step 1: Write tests** (fake stage with a position ledger + soft limits, fake light/spectrometer/camera, fixture mask provider):
  - **Dry-run `plan()`** emits the ordered action sequence (move-to-wafer, capture, per-center moves, per-point ×2 measure, return-to-center) without touching hardware — mirror `RamanWorkflow.plan()` style.
  - Refuses (raises `SafetyError`) when a stage axis is `unknown`.
  - Out-of-range point: `on_out_of_range="skip"` skips it and records `skipped`; `"abort"` raises.
  - Returns to wafer center after each sample (assert the fake stage's move log).
  - Each point measured `repeats_per_point` times; burn flag recorded when the two fixture spectra differ over threshold.
  - Manifest structure: wafer → centers → points with pixel+stage coords, roles, burn flags, statuses, output paths.
  - **Resume**: given a manifest with some points done, a re-run skips completed points.
- [x] **Step 2: Run red.**
- [x] **Step 3: Implement** `TrayScanWorkflow` with `plan()` (dry-run action list) and `run()`; a `.real(...)` constructor style like `RamanWorkflow.real`. Compute relative moves from the stage's current ledger position (add a small position accessor on the stage if needed — do not rewrite the stage protocol). Wrap each point measurement via the existing single-point acquisition. Make it interruptible (write manifest incrementally) and resumable (skip points already `done` in an existing manifest).
- [x] **Step 4: Run green.**
- [x] **Step 5: Commit** `feat(workflow): tray->wafer->sample scan orchestration`.

## Task 8: CLI `ramanctl scan` + real factory wiring

**Files:** `src/lab_auto/cli.py`, `src/lab_auto/devices/factory.py`, `tests/test_scan_cli.py`.

- [x] **Step 1: Write tests.**
  - `ramanctl scan tray --config configs/tray_scan.example.yaml --dry-run` exits 0 and prints the planned action sequence (incl. wafer moves, captures, per-point measures, returns).
  - `--real` routes through `DeviceFactory.create_tray_scan_workflow` (patched/fake factory in tests, mirroring `test_hardware_cli.py` patterns) and never touches real hardware in the test.
  - Invalid config / `unknown` stage state surface as recoverable CLI failures (nonzero exit, message), consistent with existing CLI error handling.
- [x] **Step 2: Run red.**
- [x] **Step 3: Implement** the `scan` subcommand (mirror the `workflow single` command: `--config`, `--devices-config`, `--dry-run`/`--real`, `--yes`) and `DeviceFactory.create_tray_scan_workflow` (compose stage+spectrometer+camera+light like `create_single_point_workflow`, with the same finally-close cleanup; the mask provider on real hardware = camera capture + recognition hook, left as an injection point / TODO for the recognition code).
- [x] **Step 4: Run green** (`tests/test_scan_cli.py` + `tests/test_hardware_cli.py`).
- [x] **Step 5: Commit** `feat(cli): add ramanctl scan tray command`.

## Task 9: Deferred hardware acceptance + full verification

**Files:** `docs/phase2-hardware-acceptance.md` (add M2 section), final regression.

- [x] **Step 1: Add an M2 (tray scan) section** to `docs/phase2-hardware-acceptance.md`: preflight (stage homed; tray geometry measured; per-objective calibration captured via move-and-track; confirm image center = laser spot; recognition/mask hook wired), commands (`ramanctl scan tray --real --yes`), and pass criteria (refuses on `unknown` stage; returns to wafer center between samples; each point ×2 with burn flagging; out-of-range handling; manifest completeness; resumable).
- [x] **Step 2: Full regression.** `PYTHONPATH=src .venv/bin/python -m pytest -q` (all prior + M2 green); dry-run `ramanctl workflow single ... --dry-run` still emits its unchanged sequence; `ramanctl scan tray ... --dry-run` emits the layered sequence.
- [x] **Step 3: Mark this plan's checkboxes done; commit** `docs(plan): mark phase2 m2 complete` (+ any acceptance doc).

---

## Final Verification

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q          # all green (295 + M2)
PYTHONPATH=src .venv/bin/python -m lab_auto scan tray --config configs/tray_scan.example.yaml --dry-run
git status --short                                     # clean except ignored runtime files
```

## Self-review checklist

- Discrete sample-center scan, NOT instrument raster. Centers extracted by us from the mask.
- Per center: center + 2 surrounding, each ×2; the two are a burn check (compared, flagged), not averaged.
- Image-center origin + per-objective affine pixel→stage. Wafer centers from tray geometry. Return to wafer center after each sample.
- Stage safety: refuse unless homed/user_zeroed; soft-limit every point; skip/abort out-of-range.
- All pure modules dependency-free and deterministic; whole milestone testable on macOS; real calibration/imaging/objectives deferred to hardware.
- No layer above `devices/raw/*` hand-writes hardware protocol. Single-point workflow reused for per-point measurement. Manifest makes runs interruptible/resumable/auditable (spec §17).
