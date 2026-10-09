import asyncio
import threading
import json
from dataclasses import replace

import pytest

from lab_auto.api.routers import system
from lab_auto.api.task_queue import TaskQueue
from lab_auto.api.websocket import manager
from lab_auto.errors import HardwareBusyError
from lab_auto.errors import ConfigError, DeviceError
from lab_auto.config import load_workflow_config
from lab_auto.workflow.raman import RamanWorkflow
from lab_auto.devices.factory import RamanPointMeasurer
from lab_auto.devices.light import PwmModbusLight
from lab_auto.processing.burn_check import compare_spectra
from test_pwm_light_adapter import CONFIG, FakeModbusSlave, _healthy_registers


def test_emergency_off_does_not_wait_for_stalled_websocket(monkeypatch):
    async def check():
        queue = TaskQueue()
        job_id = queue.create_job("single_point")
        queue.get_job(job_id).status = "running"
        release = asyncio.Event()
        off = threading.Event()

        class Socket:
            async def send_json(self, message):
                await release.wait()

        class Light(PwmModbusLight):
            def __init__(self):
                pass

            def emergency_off(self):
                off.set()

        queue._active_light = Light()
        manager.active_connections[job_id] = [Socket()]
        monkeypatch.setattr(system, "task_queue", queue)
        try:
            response = await asyncio.wait_for(system.emergency_stop(), timeout=0.5)
            assert response["laser_off"] == "confirmed"
            assert off.is_set() and queue._cancel_events[job_id].is_set()
        finally:
            release.set()
            await asyncio.gather(*manager._notifications)
            manager.active_connections.pop(job_id, None)
            queue._executor.shutdown()

    asyncio.run(check())


def test_timed_out_diagnostic_keeps_hardware_reserved_and_workflow_waits():
    async def check():
        queue = TaskQueue()
        entered = threading.Event()
        release = threading.Event()
        order = []

        def diagnostic():
            entered.set()
            assert release.wait(2)
            order.append("diagnostic")

        try:
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(queue.run_device_operation(diagnostic), timeout=0.05)
            assert entered.is_set() and queue.is_hardware_busy()
            with pytest.raises(HardwareBusyError):
                await queue.run_device_operation(lambda: None)
            work = asyncio.get_running_loop().run_in_executor(queue._executor, lambda: order.append("workflow"))
            assert not work.done()
            release.set()
            await work
            assert order == ["diagnostic", "workflow"]
        finally:
            release.set()
            queue._executor.shutdown()

    asyncio.run(check())


def test_restart_retains_results_and_marks_unfinished_jobs_failed(tmp_path):
    path = tmp_path / "jobs.json"
    original = TaskQueue()
    original.restore_jobs(path)
    completed = original.create_job("single_point")
    original.get_job(completed).status = "completed"
    original.get_job(completed).result = {"output_directory": "saved-run"}
    pending = original.create_job("single_point")
    running = original.create_job("single_point")
    original.get_job(running).status = "running"
    original._save_jobs()
    recovered = TaskQueue()
    recovered.restore_jobs(path)
    assert recovered.get_job(completed).result == {"output_directory": "saved-run"}
    for job_id in (pending, running):
        assert recovered.get_job(job_id).status == "failed"
        assert "restarted" in recovered.get_job(job_id).error
    assert recovered._queue.empty()
    original._executor.shutdown()
    recovered._executor.shutdown()


def test_capture_failure_is_persisted_and_visible_in_history(tmp_path, monkeypatch):
    from lab_auto.api.routers import history

    config = load_workflow_config("configs/single_point.example.yaml")
    config = replace(config, output=replace(config.output, directory=tmp_path))
    workflow = RamanWorkflow.simulated(config)
    def disconnect(**kwargs):
        raise DeviceError("camera disconnected")

    monkeypatch.setattr(workflow.camera, "capture", disconnect)
    with pytest.raises(DeviceError, match="disconnected"):
        workflow.run_single_point(require_confirmation=False)
    run_dir = next(tmp_path.iterdir())
    metadata = json.loads((run_dir / "metadata.json").read_text())
    assert metadata["status"] == "failed" and "disconnected" in metadata["errors"][0]
    assert metadata["config_snapshot"]["acquisition"]["exposure_ms"] == 1000
    assert metadata["software_version"]
    assert "disconnected" in (run_dir / "run.log").read_text()
    monkeypatch.setenv("LAB_AUTO_MEASUREMENTS_DIR", str(tmp_path))
    record = history._read_record(run_dir)
    assert record.status == "failed" and "disconnected" in record.error


def test_success_records_measured_conditions_and_temperature(tmp_path):
    config = load_workflow_config("configs/single_point.example.yaml")
    config = replace(config, output=replace(config.output, directory=tmp_path), optics=replace(config.optics, excitation_wavelength_nm=532, laser_power_mw=0.1))
    workflow = RamanWorkflow.simulated(config)
    run_dir = workflow.run_single_point(require_confirmation=False)
    metadata = json.loads((run_dir / "metadata.json").read_text())
    assert metadata["excitation"]["wavelength_nm"] == 532
    assert metadata["excitation"]["power_mw"] == 0.1
    assert metadata["camera"]["temperature_c"] == workflow.camera.temperature_c()


def test_burn_check_uses_corrected_signal_and_rejects_saturation(tmp_path):
    from types import SimpleNamespace

    config = load_workflow_config("configs/single_point.example.yaml")
    raman = SimpleNamespace(config=config, run_single_point=lambda **kwargs: tmp_path)
    measurer = RamanPointMeasurer(raman)
    (tmp_path / "raw.csv").write_text("intensity_raw\n1001\n1001\n")
    corrected = tmp_path / "corrected.csv"
    corrected.write_text("intensity_corrected,saturated_raw\n1,false\n1,false\n")
    kwargs = dict(point_id="p", x_um=0, y_um=0, role="center", repeat=0, require_confirmation=False)
    a = measurer.measure_point(**kwargs).intensities
    corrected.write_text("intensity_corrected,saturated_raw\n0,false\n0,false\n")
    b = measurer.measure_point(**kwargs).intensities
    assert compare_spectra(a, b, threshold=0.1)["burned"]
    corrected.write_text("intensity_corrected,saturated_raw\n1,true\n1,false\n")
    with pytest.raises(DeviceError, match="saturated"):
        measurer.measure_point(**kwargs)


@pytest.mark.parametrize("values", [[0, 0], [float("nan"), 1], [float("inf"), 1]])
def test_invalid_burn_reference_never_passes(values):
    with pytest.raises(ConfigError):
        compare_spectra(values, [1, 1], threshold=0.1)


def test_emergency_off_prevents_reenabling_the_same_light_handle():
    light = PwmModbusLight(CONFIG, transport=FakeModbusSlave(registers=_healthy_registers()))
    light.emergency_off()
    with pytest.raises(DeviceError, match="emergency-stopped"):
        light.laser_on()
    assert light.laser_state == "off_confirmed"
