import asyncio
import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import HTTPException, WebSocketException

import lab_auto.api.task_queue as task_queue_module
from lab_auto.api.models import JobProgress, JobStatus, SinglePointRequest
from lab_auto.api.routers import workflow
from lab_auto.api.task_queue import TaskQueue
from lab_auto.config import load_workflow_config
from lab_auto.errors import ConfigError, WorkflowCancelled


def _valid_workflow_config(devices_path):
    return replace(
        load_workflow_config("configs/single_point.example.yaml"),
        devices_config=Path(devices_path),
    )


def test_single_point_request_defaults_to_dry_run():
    request = SinglePointRequest(config_path="configs/single_point.example.yaml")

    assert request.mode == "dry_run"
    assert request.confirm_real is False


def test_real_mode_requires_explicit_confirmation_before_queueing(tmp_path, monkeypatch):
    config = tmp_path / "single.yaml"
    config.write_text("sample: {id: sample-001}\n", encoding="utf-8")

    class QueueStub:
        created = False

        def create_job(self, job_type):
            self.created = True
            return "job-1"

    queue = QueueStub()
    monkeypatch.setattr(workflow, "task_queue", queue)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(workflow.start_single_point(SinglePointRequest(config_path=str(config), mode="real")))

    assert exc_info.value.status_code == 400
    assert queue.created is False


def test_real_confirmation_is_passed_to_queue(tmp_path, monkeypatch):
    config = tmp_path / "single.yaml"
    config.write_text("sample: {id: sample-001}\n", encoding="utf-8")

    class QueueStub:
        submitted = None

        def create_job(self, job_type):
            return "job-1"

        async def submit_single_point(self, **kwargs):
            self.submitted = kwargs

        def get_job(self, job_id):
            return JobStatus(
                id=job_id,
                type="single_point",
                status="pending",
                progress=JobProgress(),
                created_at="2026-01-01T00:00:00+00:00",
            )

    queue = QueueStub()
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(workflow, "task_queue", queue)
    monkeypatch.setattr(
        workflow,
        "load_workflow_config",
        lambda *args, **kwargs: _valid_workflow_config(config),
    )
    # Real mode now loads the devices config to reject a manual light; give it a
    # pwm_modbus source so the confirmed real request is accepted and forwarded.
    monkeypatch.setattr(
        workflow,
        "load_devices_config",
        lambda *args, **kwargs: SimpleNamespace(light=SimpleNamespace(type="pwm_modbus")),
    )

    job = asyncio.run(workflow.start_single_point(
        SinglePointRequest(config_path=str(config), mode="real", confirm_real=True)
    ))

    assert job.id == "job-1"
    assert queue.submitted["confirm_real"] is True


def test_router_rejects_invalid_acquisition_before_queueing(tmp_path, monkeypatch):
    devices = tmp_path / "devices.yaml"
    devices.write_text(Path("configs/devices.example.yaml").read_text(encoding="utf-8"))
    data = yaml.safe_load(Path("configs/single_point.example.yaml").read_text(encoding="utf-8"))
    data["devices_config"] = "devices.yaml"
    data["acquisition"]["exposure_ms"] = 60_001
    (tmp_path / "single.yaml").write_text(yaml.safe_dump(data))

    class QueueStub:
        created = False

        def create_job(self, job_type):
            self.created = True

    queue = QueueStub()
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(workflow, "task_queue", queue)

    # ConfigError is mapped to HTTP 400 by the app-level exception handler.
    with pytest.raises(ConfigError, match="safety cap"):
        asyncio.run(workflow.start_single_point(SinglePointRequest(config_path="single.yaml")))

    assert queue.created is False


def _task(mode, confirm_real, *, config_path="config.yaml", devices_path=None, **overrides):
    return {
        "job_id": "job-1",
        "config_path": config_path,
        "devices_path": devices_path,
        "mode": mode,
        "confirm_real": confirm_real,
        **overrides,
    }


def test_queue_passes_real_confirmation_to_workflow(monkeypatch):
    queue = TaskQueue()
    real_workflow = RealWorkflowStub()

    class FactoryStub:
        def create_single_point_workflow(self, workflow_config, devices_config):
            return real_workflow

    monkeypatch.setattr(
        task_queue_module,
        "load_workflow_and_devices",
        lambda *args, **kwargs: (
            _valid_workflow_config("devices.yaml"),
            SimpleNamespace(light=SimpleNamespace(type="pwm_modbus")),
        ),
    )
    queue._factory = FactoryStub()

    result = queue._run_single_point_sync(_task("real", True), threading.Event())

    assert result["mode"] == "real"
    assert real_workflow.calls == [("run_single_point", True), ("close",)]


def test_task_queue_uses_one_hardware_worker():
    assert TaskQueue()._executor._max_workers == 1


def test_task_queue_prunes_old_terminal_jobs():
    queue = TaskQueue()
    first = None
    for _ in range(101):
        job_id = queue.create_job("single_point")
        first = first or job_id
        queue.get_job(job_id).status = "completed"

    assert len(queue.list_jobs()) == 100
    assert queue.get_job(first) is None


def test_simulated_result_contains_spectrum_and_applies_overrides(tmp_path):
    data = yaml.safe_load(Path("configs/single_point.example.yaml").read_text(encoding="utf-8"))
    data["output"]["directory"] = str(tmp_path / "output")
    workflow_path = tmp_path / "single.yaml"
    workflow_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    devices_path = Path("configs/devices.example.yaml").resolve()
    queue = TaskQueue()

    result = queue._run_single_point_sync(
        _task(
            "simulated",
            False,
            config_path=str(workflow_path),
            devices_path=str(devices_path),
            sample_id="override-001",
            operator="测试员",
            subtract_background=False,
        ),
        threading.Event(),
    )

    assert result["spectrum"]["raw"]
    assert result["spectrum"]["corrected"] is None
    assert len(result["x"]) == len(result["spectrum"]["raw"])
    assert result["metadata"]["sample_id"] == "override-001"
    assert result["metadata"]["operator"] == "测试员"
    assert queue._active_devices_path is None
    assert queue.safety_devices_path() is None  # simulation must not replace the real safety target


class RealWorkflowStub:
    def __init__(self):
        self.calls = []
        self.light = None

    def run_single_point(self, *, require_confirmation, should_cancel=None):
        self.calls.append(("run_single_point", require_confirmation))
        return "out"

    def close(self):
        self.calls.append(("close",))


# --- cancellation: stop_job / cancel_all -------------------------------------

def _single_point_task(job_id):
    return {
        "job_id": job_id,
        "type": "single_point",
        "config_path": "c.yaml",
        "devices_path": None,
        "mode": "dry_run",
        "confirm_real": False,
    }


class BroadcastRecorder:
    """Stand-in websocket manager that records broadcast messages."""

    def __init__(self):
        self.messages = []

    def notify(self, job_id, message):
        self.messages.append((job_id, message))

    async def broadcast(self, job_id, message):
        self.messages.append((job_id, message))


def test_stop_pending_job_marks_stopped_and_worker_skips(monkeypatch):
    queue = TaskQueue()

    async def scenario():
        job_id = queue.create_job("single_point")
        assert queue.get_job(job_id).status == "pending"

        assert await queue.stop_job(job_id) is True
        assert queue.get_job(job_id).status == "stopped"
        assert queue._cancel_events[job_id].is_set()

        # On dequeue the worker must skip a job that was stopped while pending.
        ran = []

        async def fake_execute(*args, **kwargs):
            ran.append(args)

        monkeypatch.setattr(queue, "_execute_single_point", fake_execute)
        await queue._process_task(_single_point_task(job_id))

        assert ran == []
        assert queue.get_job(job_id).status == "stopped"

    asyncio.run(scenario())


def test_stop_running_job_marks_stopping_and_sets_cancel_event():
    queue = TaskQueue()

    async def scenario():
        job_id = queue.create_job("single_point")
        queue.get_job(job_id).status = "running"

        assert await queue.stop_job(job_id) is True
        # Honest semantics: not 'stopped' yet — the workflow hasn't halted.
        assert queue.get_job(job_id).status == "stopping"
        assert queue.get_job(job_id).completed_at is None
        assert queue._cancel_events[job_id].is_set()

    asyncio.run(scenario())


def test_worker_maps_workflow_cancelled_to_stopped(monkeypatch):
    queue = TaskQueue()

    async def scenario():
        job_id = queue.create_job("single_point")

        async def cancel_execute(*args, **kwargs):
            raise WorkflowCancelled("cancelled at checkpoint")

        monkeypatch.setattr(queue, "_execute_single_point", cancel_execute)
        await queue._process_task(_single_point_task(job_id))

        job = queue.get_job(job_id)
        assert job.status == "stopped"  # NOT failed, NOT completed
        assert job.error is None

    asyncio.run(scenario())


def test_worker_does_not_overwrite_stopped_with_completed(monkeypatch):
    # A stop that lands as WorkflowCancelled must stay 'stopped'; the natural
    # completion path must not run afterwards.
    queue = TaskQueue()
    recorder = BroadcastRecorder()
    monkeypatch.setattr(task_queue_module, "manager", recorder)

    async def scenario():
        job_id = queue.create_job("single_point")

        async def cancel_execute(*args, **kwargs):
            raise WorkflowCancelled("cancelled")

        monkeypatch.setattr(queue, "_execute_single_point", cancel_execute)
        await queue._process_task(_single_point_task(job_id))

        assert queue.get_job(job_id).status == "stopped"
        statuses = [m.get("status") for (_, m) in recorder.messages]
        assert "completed" not in statuses
        assert statuses[-1] == "stopped"

    asyncio.run(scenario())


def test_completed_before_stop_took_effect_is_reported_honestly(monkeypatch):
    # Stop requested mid-run but the workflow finished before observing it:
    # report 'completed' with an honest note (not 'stopped').
    queue = TaskQueue()
    recorder = BroadcastRecorder()
    monkeypatch.setattr(task_queue_module, "manager", recorder)

    async def scenario():
        job_id = queue.create_job("single_point")
        queue._cancel_events[job_id].set()  # a stop was requested

        async def race_execute(*args, **kwargs):
            # stop_job flipped status to 'stopping' while we were running,
            # but the workflow completed without hitting a checkpoint.
            queue.get_job(job_id).status = "stopping"

        monkeypatch.setattr(queue, "_execute_single_point", race_execute)
        await queue._process_task(_single_point_task(job_id))

        job = queue.get_job(job_id)
        assert job.status == "completed"
        completed = [m for (_, m) in recorder.messages if m.get("status") == "completed"]
        assert completed[-1]["message"] == "停止请求生效前任务已完成"

    asyncio.run(scenario())


def test_worker_top_level_error_fails_job_and_calls_task_done(monkeypatch):
    # A bug outside the per-job handler must fail the job (never leave it running)
    # and still call task_done so the queue does not wedge.
    queue = TaskQueue()

    async def scenario():
        job_id = queue.create_job("single_point")
        await queue._queue.put(_single_point_task(job_id))

        async def boom(task):
            raise RuntimeError("worker exploded")

        monkeypatch.setattr(queue, "_process_task", boom)
        # Run one worker iteration by hand: mimic the worker body.
        worker = asyncio.create_task(queue._worker())
        await queue._queue.join()  # returns only once task_done() was called
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass

        job = queue.get_job(job_id)
        assert job.status == "failed"
        assert "worker exploded" in job.error

    asyncio.run(scenario())


def test_cancel_all_signals_broadcasts_and_updates_statuses(monkeypatch):
    queue = TaskQueue()
    recorder = BroadcastRecorder()
    monkeypatch.setattr(task_queue_module, "manager", recorder)

    async def scenario():
        pending = queue.create_job("single_point")
        running = queue.create_job("single_point")
        queue.get_job(running).status = "running"
        finished = queue.create_job("single_point")
        queue.get_job(finished).status = "completed"

        affected = await queue.cancel_all()

        assert set(affected) == {pending, running}
        assert queue.get_job(pending).status == "stopped"
        assert queue.get_job(running).status == "stopping"
        assert queue._cancel_events[pending].is_set()
        assert queue._cancel_events[running].is_set()
        assert finished not in affected
        statuses = {job_id: message["status"] for job_id, message in recorder.messages}
        assert statuses == {pending: "stopped", running: "stopping"}

    asyncio.run(scenario())


# --- hardware-busy tracking (is_hardware_busy / _active_job_id) -------------

def test_is_hardware_busy_set_during_processing_and_cleared_after(monkeypatch):
    queue = TaskQueue()

    async def scenario():
        job_id = queue.create_job("single_point")
        assert queue.is_hardware_busy() is False

        observed = {}

        async def fake_execute(*args, **kwargs):
            observed["busy_during"] = queue.is_hardware_busy()
            observed["active_job_id"] = queue._active_job_id

        monkeypatch.setattr(queue, "_execute_single_point", fake_execute)
        await queue._process_task(_single_point_task(job_id))

        assert observed["busy_during"] is True
        assert observed["active_job_id"] == job_id
        assert queue.is_hardware_busy() is False
        assert queue._active_job_id is None

    asyncio.run(scenario())


def test_is_hardware_busy_cleared_even_when_job_fails(monkeypatch):
    queue = TaskQueue()

    async def scenario():
        job_id = queue.create_job("single_point")

        async def boom(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(queue, "_execute_single_point", boom)
        await queue._process_task(_single_point_task(job_id))

        assert queue.get_job(job_id).status == "failed"
        assert queue.is_hardware_busy() is False
        assert queue._active_job_id is None

    asyncio.run(scenario())


def test_is_hardware_busy_false_for_pending_job_never_dequeued():
    # A job only sitting in _jobs/pending (never handed to _process_task) must
    # not be reported as busy -- busy means the hardware executor is actively
    # working on it, not merely that a job exists.
    queue = TaskQueue()
    queue.create_job("single_point")

    assert queue.is_hardware_busy() is False


# --- API-layer rejection of dangerous combinations ---------------------------

def test_router_rejects_confirm_real_in_dry_run(tmp_path):
    config = tmp_path / "single.yaml"
    config.write_text("sample: {id: sample-001}\n", encoding="utf-8")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(workflow.start_single_point(
            SinglePointRequest(config_path=str(config), mode="dry_run", confirm_real=True)
        ))

    assert exc_info.value.status_code == 400
    assert "confirm_real" in exc_info.value.detail


def test_router_rejects_real_mode_manual_light(tmp_path, monkeypatch):
    config = tmp_path / "single.yaml"
    config.write_text("sample: {id: sample-001}\n", encoding="utf-8")
    monkeypatch.setenv("LAB_AUTO_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(
        workflow,
        "load_workflow_config",
        lambda *args, **kwargs: _valid_workflow_config(config),
    )
    monkeypatch.setattr(
        workflow,
        "load_devices_config",
        lambda *args, **kwargs: SimpleNamespace(light=SimpleNamespace(type="manual")),
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(workflow.start_single_point(
            SinglePointRequest(config_path=str(config), mode="real", confirm_real=True)
        ))

    assert exc_info.value.status_code == 400
    assert "pwm_modbus" in exc_info.value.detail


def test_websocket_rejects_unknown_job_before_accepting():
    with pytest.raises(WebSocketException) as exc_info:
        asyncio.run(workflow.websocket_job_progress(object(), "does-not-exist"))

    assert exc_info.value.code == 4404
