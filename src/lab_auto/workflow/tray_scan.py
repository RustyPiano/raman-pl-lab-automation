"""Tray -> wafer -> sample layered scan orchestration.

Pure-orchestration over injected devices: a stage (WayneLabs-shaped), a
``point_measurer`` (per-point single-point Raman primitive), and a
``mask_provider`` (capture + recognition on hardware; a fixture in tests).
Composes the pure M2 modules (mask centers, affine calibration, tray geometry,
scan pattern, burn check). Writes an interruptible/resumable manifest.
"""

import hashlib
import json
import math
import os
from collections.abc import Callable
from dataclasses import dataclass

from lab_auto.config import TrayScanConfig
from lab_auto.errors import ConfigError, SafetyError, WorkflowCancelled
from lab_auto.processing.burn_check import compare_spectra
from lab_auto.scan.pattern import measurement_points
from lab_auto.scan.tray import wafer_centers
from lab_auto.vision.calibration import pixel_to_stage_delta
from lab_auto.vision.mask_centers import SampleCenter, extract_centers

_HOMED_STATES = ("homed", "user_zeroed")


def _fmt(x: float, y: float) -> str:
    return f"{x:.3f},{y:.3f}"


def simulated_mask_provider(min_area: int = 1):
    """A deterministic mask provider for dry-run/preview.

    Returns one foreground blob sized to survive the configured area threshold,
    so ``plan()`` previews the full sequence without recognition code or hardware.
    """

    side = math.isqrt(min_area - 1) + 1
    blob = [[1] * side for _ in range(side)]

    def provider(wafer):
        return blob

    return provider


@dataclass
class TrayScanWorkflow:
    config: TrayScanConfig
    dry: bool
    stage: object
    point_measurer: object
    mask_provider: object
    runtime_mode: str

    @classmethod
    def dry_run(cls, config: TrayScanConfig, *, mask_provider) -> "TrayScanWorkflow":
        return cls(config, True, None, None, mask_provider, "dry_run")

    @classmethod
    def real(cls, config: TrayScanConfig, *, stage, point_measurer, mask_provider) -> "TrayScanWorkflow":
        return cls(config, False, stage, point_measurer, mask_provider, "real")

    def close(self) -> None:
        # The point measurer owns the shared device teardown (stage, spectrometer,
        # camera, light); closing the stage here too would double-close it.
        for device in (self.point_measurer, self.mask_provider):
            close = getattr(device, "close", None)
            if close is not None:
                close()

    # -- geometry helpers ------------------------------------------------

    def _centers_for(self, wafer, *, verify_space: bool = False):
        # verify_space only on the real-run path: plan()/dry-run uses the simulated
        # simulated mask for preview and never drives the stage, so the size guard (which
        # would reject that tiny mask under a sized calibration) must not fire there.
        mask = self.mask_provider(wafer)
        if verify_space:
            self._assert_mask_matches_calibration(mask)
        return extract_centers(mask, min_area=self.config.min_area)

    def _assert_mask_matches_calibration(self, mask) -> None:
        """Refuse a mask whose pixel space != the space the calibration was fit in.

        Centroids come out in mask-pixel coordinates and are mapped to stage µm by
        ``pixel_to_stage_delta`` using ``calibration.image_center``. If the mask is
        a different resolution (e.g. the model resized the image), every centroid
        maps to the wrong physical point and the laser is driven off-target. Only
        enforceable when the calibration declares its capture size (opt-in).
        """
        calib = self.config.calibration
        if calib.image_width_px is None or calib.image_height_px is None:
            return  # pixel space not declared — recommend declaring it for real runs
        height = len(mask)
        width = len(mask[0]) if height else 0
        if width != calib.image_width_px or height != calib.image_height_px:
            raise SafetyError(
                f"recognition mask is {width}x{height} but calibration declares "
                f"{calib.image_width_px}x{calib.image_height_px}; centroids would map to the "
                "wrong stage coordinates — refusing to drive the laser"
            )

    def _sample_xy(self, wafer, center):
        dx, dy = pixel_to_stage_delta(self.config.calibration, (center.pixel_x, center.pixel_y))
        return (wafer.x_um + dx, wafer.y_um + dy)

    # -- dry-run preview -------------------------------------------------

    def plan(self) -> list[str]:
        actions: list[str] = []
        for wafer in wafer_centers(self.config.tray):
            actions.append(f"move_wafer:{wafer.index}:{_fmt(wafer.x_um, wafer.y_um)}")
            actions.append(f"capture_wafer_image:{wafer.index}")
            for center in self._centers_for(wafer):
                sx, sy = self._sample_xy(wafer, center)
                for x, y, role in measurement_points((sx, sy), self.config.pattern):
                    actions.append(f"move_point:{role}:{_fmt(x, y)}")
                    for repeat in range(self.config.pattern.repeats_per_point):
                        actions.append(f"measure:{role}:rep{repeat}")
                    actions.append(f"burn_check:{role}")
                actions.append(f"return_wafer_center:{wafer.index}")
        return actions

    # -- stage movement --------------------------------------------------

    def _assert_stage_ready(self) -> None:
        for axis in ("x", "y"):
            state = self.stage.ledger.states.get(axis)
            value = getattr(state, "value", state)
            if value not in _HOMED_STATES:
                raise SafetyError(f"tray scan requires stage axis {axis} homed/user_zeroed, got {value!r}")

    def _within_limits(self, x: float, y: float) -> bool:
        limits = self.stage.config.soft_limits_um
        for axis, target in (("x", x), ("y", y)):
            low, high = limits[axis]
            if target < low or target > high:
                return False
        return True

    def _move_to(self, x: float, y: float) -> None:
        # Validate the WHOLE target before moving either axis: a bad Y must not
        # leave X parked at a half-applied, unintended coordinate.
        if not (math.isfinite(x) and math.isfinite(y)):
            raise SafetyError(f"non-finite move target: {x},{y}")
        if not self._within_limits(x, y):
            raise SafetyError(f"move target out of soft limits: {_fmt(x, y)}")
        speed = self.stage.config.default_speed
        for axis, target in (("x", x), ("y", y)):
            delta = target - self.stage.ledger.position_um[axis]
            if delta != 0:
                self.stage.move_relative(axis=axis, um=delta, speed=speed)

    # -- run -------------------------------------------------------------

    def run(self, *, require_confirmation: bool, should_cancel: Callable[[], bool] | None = None) -> dict:
        def _check_cancel() -> None:
            # Each completed point is persisted before the next checkpoint (atomic
            # per-point write below), so cancelling here always leaves a manifest on
            # disk that retains every finished point for a later resume.
            if should_cancel is not None and should_cancel():
                raise WorkflowCancelled("tray scan cancelled by stop request")

        self._assert_stage_ready()
        self.config.output.directory.mkdir(parents=True, exist_ok=True)
        manifest_path = self.config.output.directory / "manifest.json"
        manifest, done, completed_wafers = self._load_manifest(manifest_path)

        for wafer in wafer_centers(self.config.tray):
            if wafer.index in completed_wafers:
                continue  # resume: don't re-image or re-drive a finished wafer
            wafer_entry = self._wafer_entry(manifest, wafer)
            _check_cancel()  # before moving the stage to the wafer
            self._move_to(wafer.x_um, wafer.y_um)
            centers = self._resume_or_detect_centers(wafer, wafer_entry, manifest_path, manifest)
            if not centers:
                # No centers: an empty wafer, or a recognition/handoff failure that
                # returned a blank mask. Do NOT mark 'done' (that would silently skip
                # it forever on resume) — flag it so a resume re-attempts it.
                wafer_entry["status"] = "no_centers"
                self._write_manifest(manifest_path, manifest)
                continue
            for center in centers:
                sx, sy = self._sample_xy(wafer, center)
                center_entry = self._center_entry(wafer_entry, center, sx, sy)
                for x, y, role in measurement_points((sx, sy), self.config.pattern):
                    key = f"{wafer.index}:{center.label}:{role}"
                    if key in done:
                        continue
                    _check_cancel()  # before starting a new measurement point
                    point = self._measure_point(
                        wafer, center, role, x, y, require_confirmation, should_cancel
                    )
                    center_entry["points"].append(point)
                    done.add(key)
                    self._write_manifest(manifest_path, manifest)
                _check_cancel()  # before moving back to the wafer center
                self._move_to(wafer.x_um, wafer.y_um)  # return after each sample
            wafer_entry["status"] = "done"  # mark complete so a resume skips it
            self._write_manifest(manifest_path, manifest)
        self._write_manifest(manifest_path, manifest)
        return manifest

    def _resume_or_detect_centers(self, wafer, wafer_entry, manifest_path, manifest):
        """Reuse persisted centers on resume; otherwise detect them once and persist.

        Centers are persisted up front so a resumed run reuses the SAME labels.
        Re-detecting would renumber labels from a slightly different mask and
        corrupt the done-keys (re-measuring or skipping the wrong physical sample).
        """
        persisted = wafer_entry.get("centers")
        if persisted:
            return [
                SampleCenter(pixel_x=c["pixel_x"], pixel_y=c["pixel_y"], area=c["area"], label=c["label"])
                for c in persisted
            ]
        centers = self._centers_for(wafer, verify_space=True)
        for center in centers:
            sx, sy = self._sample_xy(wafer, center)
            self._center_entry(wafer_entry, center, sx, sy)  # persist before measuring any point
        self._write_manifest(manifest_path, manifest)
        return centers

    def _measure_point(
        self, wafer, center, role, x, y, require_confirmation, should_cancel
    ) -> dict:
        if not self._within_limits(x, y):
            if self.config.on_out_of_range == "abort":
                raise SafetyError(f"measurement point out of soft limits: {_fmt(x, y)}")
            return {"role": role, "x_um": x, "y_um": y, "status": "skipped", "burn": None, "outputs": []}

        self._move_to(x, y)
        point_id = f"w{wafer.index}-c{center.label}"
        spectra = []
        outputs = []
        for repeat in range(self.config.pattern.repeats_per_point):
            result = self.point_measurer.measure_point(
                point_id=point_id,
                x_um=x,
                y_um=y,
                role=role,
                repeat=repeat,
                require_confirmation=require_confirmation,
                should_cancel=should_cancel,
            )
            spectra.append(list(result.intensities))
            outputs.append(str(result.output_path))
        burn = self._burn_check(spectra)
        return {"role": role, "x_um": x, "y_um": y, "status": "done", "burn": burn, "outputs": outputs}

    def _burn_check(self, spectra) -> dict:
        # Compare every consecutive repeat pair; flag burned if any pair exceeds
        # the threshold (so repeats_per_point > 2 is not silently dropped).
        deviation = 0.0
        burned = False
        for a, b in zip(spectra, spectra[1:]):
            result = compare_spectra(
                a,
                b,
                metric=self.config.pattern.burn_metric,
                threshold=self.config.pattern.burn_threshold,
            )
            deviation = max(deviation, result["deviation"])
            burned = burned or result["burned"]
        return {"deviation": deviation, "burned": burned}

    # -- manifest --------------------------------------------------------

    def _config_fingerprint(self) -> dict:
        """Identity of every experiment condition a manifest was produced under.

        A resume under any changed sample, optical, acquisition, geometry, or
        pattern condition would otherwise skip or mix incompatible measurements.
        """
        c = self.config
        devices_path = c.devices_config.resolve()
        try:
            devices_digest = hashlib.sha256(devices_path.read_bytes()).hexdigest()
        except OSError:
            devices_digest = None
        return {
            "runtime_mode": self.runtime_mode,
            "devices_config": [str(devices_path), devices_digest],
            "sample": [c.sample.id, c.sample.operator],
            "optics": [
                c.optics.entrance_port,
                c.optics.exit_port,
                c.optics.grating,
                c.optics.center_wavelength_nm,
                c.optics.slit_width_um,
            ],
            "acquisition": [
                c.acquisition.exposure_ms,
                c.acquisition.gain,
                c.acquisition.read_mode,
                c.acquisition.frames,
                c.acquisition.subtract_background,
            ],
            "output_formats": list(c.output.formats),
            "tray": [c.tray.rows, c.tray.cols, c.tray.pitch_x_um, c.tray.pitch_y_um,
                     c.tray.first_cell_offset_x_um, c.tray.first_cell_offset_y_um, c.tray.order],
            "calibration": [c.calibration.objective,
                            c.calibration.a11, c.calibration.a12, c.calibration.a21, c.calibration.a22,
                            c.calibration.image_center_px, c.calibration.image_center_py,
                            c.calibration.image_width_px, c.calibration.image_height_px],
            "pattern": [c.pattern.repeats_per_point, c.pattern.surrounding_count,
                        c.pattern.surrounding_distance_um, list(c.pattern.surrounding_angles_deg),
                        c.pattern.burn_metric, c.pattern.burn_threshold],
            "min_area": c.min_area,
            "on_out_of_range": c.on_out_of_range,
        }

    def _load_manifest(self, path):
        if path.exists():
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                raise ConfigError(f"existing manifest is corrupt/unreadable (delete to restart): {path}") from exc
            existing = manifest.get("config_fingerprint")
            if existing != self._config_fingerprint():
                raise ConfigError(
                    f"manifest at {path} was produced under a different experiment configuration; "
                    "use a fresh output directory or the matching config"
                )
            done = set()
            completed_wafers = set()
            for wafer in manifest.get("wafers", []):
                if wafer.get("status") == "done":
                    completed_wafers.add(wafer["index"])
                for center in wafer.get("centers", []):
                    for point in center.get("points", []):
                        if point.get("status") in ("done", "skipped"):
                            done.add(f"{wafer['index']}:{center['label']}:{point['role']}")
            return manifest, done, completed_wafers
        manifest = {
            "sample_id": self.config.sample.id,
            "operator": self.config.sample.operator,
            "runtime_mode": self.runtime_mode,
            "config_fingerprint": self._config_fingerprint(),
            "wafers": [],
        }
        return manifest, set(), set()

    def _wafer_entry(self, manifest, wafer) -> dict:
        for entry in manifest["wafers"]:
            if entry["index"] == wafer.index:
                return entry
        entry = {
            "index": wafer.index,
            "row": wafer.row,
            "col": wafer.col,
            "x_um": wafer.x_um,
            "y_um": wafer.y_um,
            "centers": [],
        }
        manifest["wafers"].append(entry)
        return entry

    def _center_entry(self, wafer_entry, center, sx, sy) -> dict:
        for entry in wafer_entry["centers"]:
            if entry["label"] == center.label:
                return entry
        entry = {
            "label": center.label,
            "pixel_x": center.pixel_x,
            "pixel_y": center.pixel_y,
            "area": center.area,
            "stage_x_um": sx,
            "stage_y_um": sy,
            "points": [],
        }
        wafer_entry["centers"].append(entry)
        return entry

    def _write_manifest(self, path, manifest) -> None:
        # Atomic: write a sibling temp file then os.replace it in. A crash/power-loss
        # mid-write then leaves the previous complete manifest intact (write_text
        # truncates first, so a partial write would otherwise make resume unloadable).
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        os.replace(tmp, path)
