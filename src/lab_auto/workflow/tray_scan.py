"""Tray -> wafer -> sample layered scan orchestration.

Pure-orchestration over injected devices: a stage (WayneLabs-shaped), a
``point_measurer`` (per-point single-point Raman primitive), and a
``mask_provider`` (capture + recognition on hardware; a fixture in tests).
Composes the pure M2 modules (mask centers, affine calibration, tray geometry,
scan pattern, burn check). Writes an interruptible/resumable manifest.
"""

import json
from dataclasses import dataclass

from lab_auto.config import TrayScanConfig
from lab_auto.errors import SafetyError
from lab_auto.processing.burn_check import compare_spectra
from lab_auto.scan.pattern import measurement_points
from lab_auto.scan.tray import wafer_centers
from lab_auto.vision.calibration import pixel_to_stage_delta
from lab_auto.vision.mask_centers import extract_centers

_HOMED_STATES = ("homed", "user_zeroed")


def _fmt(x: float, y: float) -> str:
    return f"{x:.3f},{y:.3f}"


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

    # -- geometry helpers ------------------------------------------------

    def _centers_for(self, wafer):
        mask = self.mask_provider(wafer)
        return extract_centers(mask, min_area=self.config.min_area)

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
        speed = self.stage.config.default_speed
        for axis, target in (("x", x), ("y", y)):
            delta = target - self.stage.ledger.position_um[axis]
            if delta != 0:
                self.stage.move_relative(axis=axis, um=delta, speed=speed)

    # -- run -------------------------------------------------------------

    def run(self, *, require_confirmation: bool) -> dict:
        self._assert_stage_ready()
        self.config.output.directory.mkdir(parents=True, exist_ok=True)
        manifest_path = self.config.output.directory / "manifest.json"
        manifest, done = self._load_manifest(manifest_path)

        for wafer in wafer_centers(self.config.tray):
            wafer_entry = self._wafer_entry(manifest, wafer)
            self._move_to(wafer.x_um, wafer.y_um)
            for center in self._centers_for(wafer):
                sx, sy = self._sample_xy(wafer, center)
                center_entry = self._center_entry(wafer_entry, center, sx, sy)
                for x, y, role in measurement_points((sx, sy), self.config.pattern):
                    key = f"{wafer.index}:{center.label}:{role}"
                    if key in done:
                        continue
                    point = self._measure_point(wafer, center, role, x, y, require_confirmation)
                    center_entry["points"].append(point)
                    done.add(key)
                    self._write_manifest(manifest_path, manifest)
                self._move_to(wafer.x_um, wafer.y_um)  # return after each sample
        self._write_manifest(manifest_path, manifest)
        return manifest

    def _measure_point(self, wafer, center, role, x, y, require_confirmation) -> dict:
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
            )
            spectra.append(list(result.intensities))
            outputs.append(str(result.output_path))
        burn = compare_spectra(
            spectra[0],
            spectra[1],
            metric=self.config.pattern.burn_metric,
            threshold=self.config.pattern.burn_threshold,
        )
        return {"role": role, "x_um": x, "y_um": y, "status": "done", "burn": burn, "outputs": outputs}

    # -- manifest --------------------------------------------------------

    def _load_manifest(self, path):
        if path.exists():
            manifest = json.loads(path.read_text(encoding="utf-8"))
            done = set()
            for wafer in manifest.get("wafers", []):
                for center in wafer.get("centers", []):
                    for point in center.get("points", []):
                        if point.get("status") in ("done", "skipped"):
                            done.add(f"{wafer['index']}:{center['label']}:{point['role']}")
            return manifest, done
        manifest = {
            "sample_id": self.config.sample.id,
            "operator": self.config.sample.operator,
            "runtime_mode": self.runtime_mode,
            "wafers": [],
        }
        return manifest, set()

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
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
