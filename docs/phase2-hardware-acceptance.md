# Phase 2 · M1 PWM Light Backend — Hardware Acceptance

Run on the Windows 64-bit lab computer only, after the development work is complete.
This gate is intentionally deferred until then, consistent with Phase 1.

## Preflight (confirm with 老师 / 厂家 before powering anything)

1. Which PWM channel drives the **laser**, and which drives the **white LED** — read these CH numbers from the **MAPS system-config "mode" page** (Image mode = LED on; Test mode = LED off + laser on; 5 channels total, can probe one by one).
2. Actual **COM port**, non-zero **station id**, and RS485 wiring.
3. Per-channel **frequency_hz** and **duty_percent**, and the default-off requirement.
4. The regulated-supply output terminal wiring is confirmed safe to energize.
5. Laser is manually controllable and **initially off**; the laser interlock state, if any, is readable.
6. Copy `configs/devices.example.yaml` to `configs/devices.real.yaml`, set
   `runtime.mode: real`, switch the `light` block to the `pwm_modbus` form, and fill
   the confirmed port / station id / channel mapping / setpoints.

## Commands

```bash
ramanctl devices doctor --config configs/devices.real.yaml --real
ramanctl workflow single --config configs/single_point.yaml --devices-config configs/devices.real.yaml --real --yes
```

## Pass Criteria (spec 6.5 / 12.2 / 12.3)

- `Reg1` reads back as decimal `50` (`0x0032`, cable bytes `00 32`) before any channel opens; a value > 5.0 V is never written.
- Before opening any channel, non-target / unknown channels (`Reg17-Reg21`) read back `0`.
- Target-channel frequency (`Reg2-Reg11`) and duty (`Reg12-Reg16`) read back equal to the configured `frequency_hz` / `duty_percent`; a mismatch refuses laser-on.
- After `laser_on`, the target output-state register reads back `1`; only then is `laser_state = on_confirmed`.
- `led_on` sets only `led_state`; it never satisfies the laser precondition for sample acquisition.
- `laser_off`, `led_off`, and every failure path best-effort close all configured channels and read back `0`; on read-back failure the run prompts manual laser-off confirmation.
- No frame writes `Reg23`, `Reg24`, or `Reg25`; no frame uses `station_id = 0`.
- Every Modbus write is confirmed by a `0x03` read-back; a `0x06` / `0x10` echo alone is not treated as confirmation.
- Read-backs come from fully valid responses (CRC correct, station equals the requested non-zero station, function code matches and is not an exception, byte count consistent).
- The PWM serial port is opened once for the workflow lifecycle and closed through the workflow `finally` path.

---

# Phase 2 · M2 Tray → Wafer → Sample Layered Scan — Hardware Acceptance

Run on the Windows 64-bit lab computer only, after the development work is complete.
This gate is intentionally deferred, consistent with Phase 1 and M1. All M2 logic
(mask centers, affine calibration, tray geometry, scan pattern, burn check,
orchestration) is unit-tested on the dev machine; only the values below and the
recognition/imaging hook require hardware.

## Preflight (confirm with 老师 / 厂家 before running)

1. **Stage homed.** X and Y are `homed` or `user_zeroed` (mechanical-limit init); the
   scan refuses to start otherwise (spec §12.1).
2. **Tray geometry measured.** Fill `tray` in `configs/tray_scan.real.yaml`: `rows`,
   `cols`, `pitch_x_um`/`pitch_y_um`, `first_cell_offset_x_um`/`_y_um`, and `order`
   (`row_major` | `serpentine`) so wafer centers land on real cell centers.
3. **Per-objective calibration captured.** With the working objective, command known
   stage moves (e.g. `(D,0)` and `(0,D)`), track the imaged feature pixel shift, and
   `fit_affine` the `A` matrix; record `a11..a22`, `image_center_px`, `image_center_py`,
   and `objective` in `calibration`. Repeat per objective actually used.
4. **Confirm image center = laser spot.** Verify the measurement point (laser spot)
   coincides with the image center used as the calibration origin; if not, record the
   laser-spot pixel and add it as the calibration origin (additive change, not structural).
5. **Recognition/mask hook wired.** Inject the recognition `mask_provider`
   (camera capture → recognition mask) via `create_tray_scan_workflow(mask_provider=...)`;
   the unwired default refuses to run. Confirm mask form (binary/labeled 2D grid) and
   `min_area`.
6. **Burn-check threshold.** Set `pattern.burn_threshold` (and `burn_metric`) from a
   known-good repeat pair so genuine burns flag and stable spectra do not.
7. **PWM laser interlock** (from M1) is in place; laser power (half-wave plate) is set
   by the separate power module — not part of M2.

## Commands

```bash
ramanctl scan tray --config configs/tray_scan.real.yaml --dry-run            # preview the layered sequence
ramanctl scan tray --config configs/tray_scan.real.yaml --devices-config configs/devices.real.yaml --real --yes
```

## Pass Criteria (spec §4.4 / §12.1 / §17)

- Refuses to start (`SafetyError`) unless stage X and Y are `homed`/`user_zeroed`.
- Visits wafer centers in the configured tray order; images each wafer once.
- Extracts sample centers from the mask (connected components → centroid) and moves to
  each via the per-objective affine `pixel_to_stage_delta` (image center = origin).
- Each detected center measures the center point + the parameterized surrounding points;
  each point is acquired `repeats_per_point` times and the two are compared as a burn
  check (both spectra kept; deviation over threshold flags `burned` in the manifest).
- Returns to the wafer center after every sample (error does not accumulate).
- Every target point passes the stage soft-limit check; out-of-range points are skipped
  (`on_out_of_range: skip`) or abort the run (`abort`), as configured.
- The manifest records wafer → sample center → points with pixel + stage coords, roles,
  burn flags, statuses, and output paths; it is written incrementally so an interrupted
  run is resumable (a re-run skips points already `done`).
- All owned devices (stage, spectrometer, camera, light) are closed through the
  workflow `finally` path.
