# Phase 1 Hardware Acceptance

> **Result (2026-06-24): PASSED on the lab Windows machine.** Stage (COM4),
> Zolix spectrometer (DLL v24.5.0), DField camera (2048×264), and the full
> single-point Raman workflow (background + sample + background-subtraction +
> outputs) all ran on real hardware; 355/355 unit tests green on Python 3.13
> 64-bit. Real COM/channel/DLL map and full evidence:
> [`hardware-acceptance-report-20260624.md`](hardware-acceptance-report-20260624.md).
> Stage `resolution_um=0.04` and `soft_limits_um` are still placeholder/old-code
> values pending on-stage measurement.

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
- `metadata.json` reports `"runtime_mode": "real"` in real mode and includes `camera.saturated_count`, `camera.saturation_threshold`, and `camera.raw_frames_count`.
- `corrected.csv` subtracts the captured `background.csv` values, not placeholder constants.
- DField workflow capture opens the camera once per raw client lifecycle and closes it through the workflow `finally` path.
- Any failure path prompts the user to confirm laser-off state.
