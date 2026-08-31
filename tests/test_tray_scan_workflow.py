import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from lab_auto.config import (
    AcquisitionConfig,
    Calibration,
    OpticsConfig,
    OutputConfig,
    SampleConfig,
    ScanPattern,
    TrayLayout,
    TrayScanConfig,
)
from lab_auto.devices.waynelabs_stage import AxisState
from lab_auto.errors import ConfigError, SafetyError, WorkflowCancelled
from lab_auto.scan.pattern import measurement_points
from lab_auto.scan.tray import wafer_centers
from lab_auto.vision.calibration import pixel_to_stage_delta
from lab_auto.vision.mask_centers import extract_centers
from lab_auto.workflow.tray_scan import TrayScanWorkflow


# --- fakes -------------------------------------------------------------

class FakeStage:
    def __init__(self, *, states, position, soft_limits, default_speed=10):
        self.ledger = SimpleNamespace(states=dict(states), position_um=dict(position))
        self.config = SimpleNamespace(soft_limits_um=soft_limits, default_speed=default_speed)
        self.landings = []  # (x, y) after each move command pair

    def move_relative(self, *, axis, um, speed):
        self.ledger.position_um[axis] = self.ledger.position_um[axis] + um
        return [f"move:{axis}:{um}"]

    def close(self):
        raise AssertionError("tray-scan workflow must not close the stage directly; the measurer owns it")


class FakeMeasurer:
    def __init__(self, intensity_fn):
        self.intensity_fn = intensity_fn
        self.calls = []
        self.cancel_callbacks = []
        self.mask_calls = 0
        self.closed = False

    def measure_point(
        self, *, point_id, x_um, y_um, role, repeat, require_confirmation, should_cancel=None
    ):
        self.calls.append((point_id, role, repeat))
        self.cancel_callbacks.append(should_cancel)
        return SimpleNamespace(
            intensities=self.intensity_fn(role, repeat),
            output_path=f"out/{point_id}-{role}-rep{repeat}",
        )

    def close(self):
        self.closed = True


def _homed_stage(**overrides):
    base = dict(
        states={"x": AxisState.HOMED, "y": AxisState.HOMED},
        position={"x": 0.0, "y": 0.0},
        soft_limits={"x": [-100000.0, 100000.0], "y": [-100000.0, 100000.0]},
    )
    base.update(overrides)
    return FakeStage(**base)


def _config(*, tray, pattern, calibration, min_area=1, on_out_of_range="skip", output_dir):
    return TrayScanConfig(
        devices_config=Path("configs/devices.example.yaml"),
        sample=SampleConfig(id="tray-test", operator="lab"),
        optics=OpticsConfig(entrance_port="side", exit_port="direct", grating=1, center_wavelength_nm=600.0, slit_width_um=100),
        acquisition=AcquisitionConfig(exposure_ms=10.0, gain="low", read_mode="fvb", frames=1, subtract_background=False),
        output=OutputConfig(directory=output_dir, formats=["csv"]),
        tray=tray,
        pattern=pattern,
        calibration=calibration,
        min_area=min_area,
        on_out_of_range=on_out_of_range,
    )


def _calib():
    # identity-ish, image center at (2,2); a blob at (1,1) gives delta (1,1).
    return Calibration(objective="x", a11=1.0, a12=0.0, a21=0.0, a22=1.0, image_center_px=2.0, image_center_py=2.0)


def _tray_1x1():
    return TrayLayout(rows=1, cols=1, pitch_x_um=1000.0, pitch_y_um=1000.0, first_cell_offset_x_um=500.0, first_cell_offset_y_um=300.0, order="row_major")


# one blob whose centroid is (1,1)
ONE_BLOB = [
    [1, 1, 0, 0, 0],
    [1, 1, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0],
]
# centroid of the 2x2 block at rows0-1, cols0-1 -> (0.5, 0.5)

TWO_BLOBS = [
    [1, 1, 0, 0, 0],
    [1, 1, 0, 0, 0],
    [0, 0, 0, 0, 0],
    [0, 0, 0, 1, 1],
    [0, 0, 0, 1, 1],
]


def _fmt(x, y):
    return f"{x:.3f},{y:.3f}"


# --- tests -------------------------------------------------------------

def test_plan_emits_ordered_actions(tmp_path):
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5, surrounding_count=1, surrounding_distance_um=10.0, surrounding_angles_deg=[0.0])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), output_dir=tmp_path)
    wf = TrayScanWorkflow.dry_run(cfg, mask_provider=lambda wafer: ONE_BLOB)
    actions = wf.plan()

    wafer = wafer_centers(cfg.tray)[0]
    center = extract_centers(ONE_BLOB, min_area=cfg.min_area)[0]
    dx, dy = pixel_to_stage_delta(cfg.calibration, (center.pixel_x, center.pixel_y))
    sx, sy = wafer.x_um + dx, wafer.y_um + dy
    pts = measurement_points((sx, sy), pattern)

    expected = [
        f"move_wafer:0:{_fmt(wafer.x_um, wafer.y_um)}",
        "capture_wafer_image:0",
        f"move_point:center:{_fmt(pts[0][0], pts[0][1])}",
        "measure:center:rep0",
        "measure:center:rep1",
        "burn_check:center",
        f"move_point:surrounding_0:{_fmt(pts[1][0], pts[1][1])}",
        "measure:surrounding_0:rep0",
        "measure:surrounding_0:rep1",
        "burn_check:surrounding_0",
        "return_wafer_center:0",
    ]
    assert actions == expected


def test_run_refuses_when_axis_unknown(tmp_path):
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5, surrounding_count=0, surrounding_distance_um=10.0, surrounding_angles_deg=[])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), output_dir=tmp_path)
    stage = _homed_stage(states={"x": AxisState.UNKNOWN, "y": AxisState.HOMED})
    wf = TrayScanWorkflow.real(cfg, stage=stage, point_measurer=FakeMeasurer(lambda r, n: [1.0]), mask_provider=lambda w: ONE_BLOB)
    with pytest.raises(SafetyError):
        wf.run(require_confirmation=False)


def test_run_measures_repeats_and_flags_burn(tmp_path):
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5, surrounding_count=0, surrounding_distance_um=10.0, surrounding_angles_deg=[])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), output_dir=tmp_path)
    stage = _homed_stage()

    def intensity(role, repeat):
        return [10.0, 10.0, 10.0] if repeat == 0 else [1.0, 1.0, 1.0]

    measurer = FakeMeasurer(intensity)
    wf = TrayScanWorkflow.real(cfg, stage=stage, point_measurer=measurer, mask_provider=lambda w: ONE_BLOB)
    manifest = wf.run(require_confirmation=False)

    # one wafer, one center, one point (center only), measured twice
    assert len(measurer.calls) == 2
    point = manifest["wafers"][0]["centers"][0]["points"][0]
    assert point["role"] == "center"
    assert point["status"] == "done"
    assert point["burn"]["burned"] is True
    assert len(point["outputs"]) == 2


def test_run_returns_to_wafer_center_after_each_sample(tmp_path):
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=10.0, surrounding_count=0, surrounding_distance_um=10.0, surrounding_angles_deg=[])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), min_area=1, output_dir=tmp_path)
    stage = _homed_stage()
    measurer = FakeMeasurer(lambda r, n: [1.0, 1.0])
    wf = TrayScanWorkflow.real(cfg, stage=stage, point_measurer=measurer, mask_provider=lambda w: TWO_BLOBS)
    wf.run(require_confirmation=False)

    wafer = wafer_centers(cfg.tray)[0]
    # ends back at the wafer center after the last sample
    assert stage.ledger.position_um["x"] == pytest.approx(wafer.x_um)
    assert stage.ledger.position_um["y"] == pytest.approx(wafer.y_um)


def test_out_of_range_skip_records_skipped(tmp_path):
    # surrounding point lands far outside a tight soft limit -> skipped
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5, surrounding_count=1, surrounding_distance_um=10000.0, surrounding_angles_deg=[0.0])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), on_out_of_range="skip", output_dir=tmp_path)
    stage = _homed_stage(soft_limits={"x": [-1000.0, 1000.0], "y": [-1000.0, 1000.0]})
    measurer = FakeMeasurer(lambda r, n: [1.0, 1.0])
    wf = TrayScanWorkflow.real(cfg, stage=stage, point_measurer=measurer, mask_provider=lambda w: ONE_BLOB)
    manifest = wf.run(require_confirmation=False)

    points = manifest["wafers"][0]["centers"][0]["points"]
    surrounding = [p for p in points if p["role"] == "surrounding_0"][0]
    assert surrounding["status"] == "skipped"


def test_out_of_range_abort_raises(tmp_path):
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5, surrounding_count=1, surrounding_distance_um=10000.0, surrounding_angles_deg=[0.0])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), on_out_of_range="abort", output_dir=tmp_path)
    stage = _homed_stage(soft_limits={"x": [-1000.0, 1000.0], "y": [-1000.0, 1000.0]})
    measurer = FakeMeasurer(lambda r, n: [1.0, 1.0])
    wf = TrayScanWorkflow.real(cfg, stage=stage, point_measurer=measurer, mask_provider=lambda w: ONE_BLOB)
    with pytest.raises(SafetyError):
        wf.run(require_confirmation=False)


def test_manifest_written_and_structured(tmp_path):
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5, surrounding_count=1, surrounding_distance_um=10.0, surrounding_angles_deg=[90.0])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), output_dir=tmp_path)
    stage = _homed_stage()
    measurer = FakeMeasurer(lambda r, n: [1.0, 1.0])
    wf = TrayScanWorkflow.real(cfg, stage=stage, point_measurer=measurer, mask_provider=lambda w: ONE_BLOB)
    manifest = wf.run(require_confirmation=False)

    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()
    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert on_disk == manifest
    wafer = manifest["wafers"][0]
    assert wafer["index"] == 0
    center = wafer["centers"][0]
    assert "pixel_x" in center and "stage_x_um" in center
    roles = [p["role"] for p in center["points"]]
    assert roles == ["center", "surrounding_0"]
    for p in center["points"]:
        assert "x_um" in p and "y_um" in p and "status" in p


def test_run_cancel_midway_preserves_completed_points(tmp_path):
    # Cancel after the first measurement point completes; the atomic per-point write
    # must leave that point persisted for a resume, and the second point unmeasured.
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5,
                          surrounding_count=1, surrounding_distance_um=10.0, surrounding_angles_deg=[0.0])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), output_dir=tmp_path)
    cancel = {"stop": False}

    class CancelingMeasurer(FakeMeasurer):
        def measure_point(self, **kwargs):
            result = super().measure_point(**kwargs)
            cancel["stop"] = True  # request a stop once the first point starts measuring
            return result

    measurer = CancelingMeasurer(lambda r, n: [1.0, 1.0])
    wf = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=measurer, mask_provider=lambda w: ONE_BLOB)

    with pytest.raises(WorkflowCancelled):
        wf.run(require_confirmation=False, should_cancel=lambda: cancel["stop"])

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    points = manifest["wafers"][0]["centers"][0]["points"]
    assert [p["role"] for p in points] == ["center"]  # surrounding_0 never measured
    assert points[0]["status"] == "done"
    assert len(points[0]["outputs"]) == 2  # first point fully completed and persisted


def test_resume_skips_completed_points(tmp_path):
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5, surrounding_count=1, surrounding_distance_um=10.0, surrounding_angles_deg=[90.0])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), output_dir=tmp_path)
    stage = _homed_stage()
    measurer = FakeMeasurer(lambda r, n: [1.0, 1.0])
    wf = TrayScanWorkflow.real(cfg, stage=stage, point_measurer=measurer, mask_provider=lambda w: ONE_BLOB)
    wf.run(require_confirmation=False)
    first_calls = len(measurer.calls)
    assert first_calls == 4  # 2 points x 2 repeats

    # re-run with the same manifest present -> all points already done -> no new measurements
    measurer2 = FakeMeasurer(lambda r, n: [1.0, 1.0])
    stage2 = _homed_stage()
    wf2 = TrayScanWorkflow.real(cfg, stage=stage2, point_measurer=measurer2, mask_provider=lambda w: ONE_BLOB)
    wf2.run(require_confirmation=False)
    assert len(measurer2.calls) == 0


def test_resume_skips_recapture_and_motion_for_completed_wafer(tmp_path):
    # A fully-completed wafer must not be re-imaged or re-driven on resume.
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5, surrounding_count=0, surrounding_distance_um=10.0, surrounding_angles_deg=[])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), output_dir=tmp_path)

    class CountingProvider:
        def __init__(self):
            self.calls = 0

        def __call__(self, wafer):
            self.calls += 1
            return ONE_BLOB

    p1 = CountingProvider()
    wf1 = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0, 1.0]), mask_provider=p1)
    wf1.run(require_confirmation=False)
    assert p1.calls == 1

    p2 = CountingProvider()
    stage2 = _homed_stage()
    wf2 = TrayScanWorkflow.real(cfg, stage=stage2, point_measurer=FakeMeasurer(lambda r, n: [1.0, 1.0]), mask_provider=p2)
    wf2.run(require_confirmation=False)
    assert p2.calls == 0  # completed wafer not re-imaged
    assert stage2.ledger.position_um == {"x": 0.0, "y": 0.0}  # stage did not move


def test_close_does_not_close_stage_directly(tmp_path):
    pattern = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5, surrounding_count=0, surrounding_distance_um=10.0, surrounding_angles_deg=[])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), output_dir=tmp_path)
    stage = _homed_stage()  # FakeStage.close() raises if called directly
    measurer = FakeMeasurer(lambda r, n: [1.0, 1.0])  # measurer owns device teardown
    wf = TrayScanWorkflow.real(cfg, stage=stage, point_measurer=measurer, mask_provider=lambda w: ONE_BLOB)
    wf.close()  # must not raise
    assert measurer.closed is True


def test_burn_check_considers_all_repeats(tmp_path):
    # repeats_per_point=3 where only the 3rd acquisition differs must still flag burned.
    pattern = ScanPattern(repeats_per_point=3, burn_metric="relative_l2", burn_threshold=0.5, surrounding_count=0, surrounding_distance_um=10.0, surrounding_angles_deg=[])
    cfg = _config(tray=_tray_1x1(), pattern=pattern, calibration=_calib(), output_dir=tmp_path)

    def intensity(role, repeat):
        return [10.0, 10.0, 10.0] if repeat < 2 else [1.0, 1.0, 1.0]

    measurer = FakeMeasurer(intensity)
    wf = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=measurer, mask_provider=lambda w: ONE_BLOB)
    manifest = wf.run(require_confirmation=False)

    assert len(measurer.calls) == 3
    point = manifest["wafers"][0]["centers"][0]["points"][0]
    assert point["burn"]["burned"] is True


# --- audit-fix regression tests ----------------------------------------

def _calib_sized(w, h):
    return Calibration(objective="x", a11=1.0, a12=0.0, a21=0.0, a22=1.0,
                       image_center_px=2.0, image_center_py=2.0, image_width_px=w, image_height_px=h)


def _single_point_pattern():
    return ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.5,
                       surrounding_count=0, surrounding_distance_um=10.0, surrounding_angles_deg=[])


def test_dry_run_plan_ignores_size_guard(tmp_path):
    # plan()/dry-run uses the 3x3 simulated mask and never drives the stage, so a
    # sized calibration must NOT make the size guard fire during preview.
    from lab_auto.workflow.tray_scan import simulated_mask_provider

    cfg = _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib_sized(640, 480), output_dir=tmp_path)
    wf = TrayScanWorkflow.dry_run(cfg, mask_provider=simulated_mask_provider())
    actions = wf.plan()  # must not raise SafetyError
    assert any(a.startswith("move_wafer:") for a in actions)


def test_mask_size_mismatch_refuses_to_drive_laser(tmp_path):
    # ONE_BLOB is 5x5; a calibration declaring 5x5 accepts it, a 3x3 mask is refused.
    cfg = _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib_sized(5, 5), output_dir=tmp_path)
    wf = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]),
                               mask_provider=lambda w: [[0, 1, 0], [0, 1, 0], [0, 0, 0]])  # 3x3
    with pytest.raises(SafetyError):
        wf.run(require_confirmation=False)


def test_mask_size_match_is_accepted(tmp_path):
    cfg = _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib_sized(5, 5), output_dir=tmp_path)
    wf = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]),
                               mask_provider=lambda w: ONE_BLOB)  # 5x5
    manifest = wf.run(require_confirmation=False)
    assert manifest["wafers"][0]["status"] == "done"


def test_empty_mask_flags_no_centers_and_resume_retries(tmp_path):
    cfg = _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib(), output_dir=tmp_path)
    calls = {"n": 0}

    def provider(wafer):
        calls["n"] += 1
        return [[0, 0, 0], [0, 0, 0], [0, 0, 0]]

    wf = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]), mask_provider=provider)
    manifest = wf.run(require_confirmation=False)
    assert manifest["wafers"][0]["status"] == "no_centers"  # NOT "done"

    # resume must re-attempt (not silently skip a non-done wafer)
    wf2 = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]), mask_provider=provider)
    wf2.run(require_confirmation=False)
    assert calls["n"] == 2


def test_resume_reuses_persisted_centers_ignoring_new_mask(tmp_path):
    cfg = _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib(), output_dir=tmp_path)
    wafer = wafer_centers(cfg.tray)[0]
    fingerprint = TrayScanWorkflow.real(
        cfg,
        stage=_homed_stage(),
        point_measurer=FakeMeasurer(lambda r, n: [1.0]),
        mask_provider=lambda w: ONE_BLOB,
    )._config_fingerprint()
    # Seed a partially-done manifest: one detected center, no points measured yet.
    (tmp_path / "manifest.json").write_text(json.dumps({
        "sample_id": cfg.sample.id, "operator": cfg.sample.operator, "runtime_mode": "real",
        "config_fingerprint": fingerprint,
        "wafers": [{
            "index": 0, "row": wafer.row, "col": wafer.col, "x_um": wafer.x_um, "y_um": wafer.y_um,
            "centers": [{"label": 1, "pixel_x": 0.5, "pixel_y": 0.5, "area": 4,
                         "stage_x_um": 0.0, "stage_y_um": 0.0, "points": []}],
        }],
    }))
    calls = {"n": 0}

    def provider(wafer):  # a DIFFERENT mask (two blobs) — must be ignored on resume
        calls["n"] += 1
        return TWO_BLOBS

    wf = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]), mask_provider=provider)
    manifest = wf.run(require_confirmation=False)
    assert calls["n"] == 0  # persisted centers reused; recognition NOT re-run
    assert len(manifest["wafers"][0]["centers"]) == 1  # the persisted single center, not two


def test_corrupt_manifest_raises_config_error(tmp_path):
    (tmp_path / "manifest.json").write_text("{ not valid json")
    cfg = _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib(), output_dir=tmp_path)
    wf = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]), mask_provider=lambda w: ONE_BLOB)
    with pytest.raises(ConfigError):
        wf.run(require_confirmation=False)


def test_config_fingerprint_mismatch_raises(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "config_fingerprint": {"tray": ["totally", "different"]}, "wafers": [],
    }))
    cfg = _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib(), output_dir=tmp_path)
    wf = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]), mask_provider=lambda w: ONE_BLOB)
    with pytest.raises(ConfigError):
        wf.run(require_confirmation=False)


def test_manifest_without_fingerprint_is_not_resumed(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"wafers": []}))
    cfg = _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib(), output_dir=tmp_path)
    wf = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]), mask_provider=lambda w: ONE_BLOB)

    with pytest.raises(ConfigError, match="different experiment configuration"):
        wf.run(require_confirmation=False)


def test_fingerprint_includes_burn_threshold(tmp_path):
    # Changing only burn_threshold must invalidate a resume (fingerprint covers it).
    cfg = _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib(), output_dir=tmp_path)
    TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]),
                          mask_provider=lambda w: ONE_BLOB).run(require_confirmation=False)
    changed = ScanPattern(repeats_per_point=2, burn_metric="relative_l2", burn_threshold=0.99,
                          surrounding_count=0, surrounding_distance_um=10.0, surrounding_angles_deg=[])
    cfg2 = _config(tray=_tray_1x1(), pattern=changed, calibration=_calib(), output_dir=tmp_path)
    wf2 = TrayScanWorkflow.real(cfg2, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]), mask_provider=lambda w: ONE_BLOB)
    with pytest.raises(ConfigError):
        wf2.run(require_confirmation=False)


def test_fingerprint_rejects_changed_acquisition(tmp_path):
    cfg = _config(
        tray=_tray_1x1(),
        pattern=_single_point_pattern(),
        calibration=_calib(),
        output_dir=tmp_path,
    )
    TrayScanWorkflow.real(
        cfg,
        stage=_homed_stage(),
        point_measurer=FakeMeasurer(lambda r, n: [1.0]),
        mask_provider=lambda w: ONE_BLOB,
    ).run(require_confirmation=False)
    changed = replace(cfg, acquisition=replace(cfg.acquisition, exposure_ms=20.0))

    with pytest.raises(ConfigError, match="different experiment configuration"):
        TrayScanWorkflow.real(
            changed,
            stage=_homed_stage(),
            point_measurer=FakeMeasurer(lambda r, n: [1.0]),
            mask_provider=lambda w: ONE_BLOB,
        ).run(require_confirmation=False)


def test_fingerprint_changes_when_devices_file_changes(tmp_path):
    devices = tmp_path / "devices.yaml"
    devices.write_text("runtime: {mode: real}")
    cfg = replace(
        _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib(), output_dir=tmp_path),
        devices_config=devices,
    )
    wf = TrayScanWorkflow.real(cfg, stage=_homed_stage(), point_measurer=FakeMeasurer(lambda r, n: [1.0]), mask_provider=lambda w: ONE_BLOB)
    before = wf._config_fingerprint()

    devices.write_text("runtime: {mode: dry_run}")

    assert wf._config_fingerprint() != before


def test_cancel_callback_reaches_each_point_measurement(tmp_path):
    cfg = _config(tray=_tray_1x1(), pattern=_single_point_pattern(), calibration=_calib(), output_dir=tmp_path)
    measurer = FakeMeasurer(lambda r, n: [1.0])
    callback = lambda: False

    TrayScanWorkflow.real(
        cfg, stage=_homed_stage(), point_measurer=measurer, mask_provider=lambda w: ONE_BLOB
    ).run(require_confirmation=False, should_cancel=callback)

    assert measurer.cancel_callbacks and all(item is callback for item in measurer.cancel_callbacks)
