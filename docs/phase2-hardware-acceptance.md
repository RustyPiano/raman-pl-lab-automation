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
