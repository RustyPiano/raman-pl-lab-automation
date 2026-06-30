import asyncio

import pytest
from fastapi import HTTPException

import lab_auto.api.task_queue as task_queue_module
from lab_auto.api.models import JobProgress, JobStatus, SinglePointRequest
from lab_auto.api.routers import workflow
from lab_auto.api.task_queue import TaskQueue
from lab_auto.errors import ConfigError


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
    monkeypatch.setattr(workflow, "task_queue", queue)

    job = asyncio.run(workflow.start_single_point(
        SinglePointRequest(config_path=str(config), mode="real", confirm_real=True)
    ))

    assert job.id == "job-1"
    assert queue.submitted["confirm_real"] is True


def test_queue_passes_real_confirmation_to_workflow(monkeypatch):
    queue = TaskQueue()
    real_workflow = RealWorkflowStub()

    class FactoryStub:
        def create_single_point_workflow(self, workflow_config, devices_config):
            return real_workflow

    monkeypatch.setattr(task_queue_module, "load_workflow_and_devices", lambda *args, **kwargs: (object(), object()))
    queue._factory = FactoryStub()

    result = queue._run_single_point_sync("config.yaml", None, "real", True, "job-1")

    assert result["mode"] == "real"
    assert real_workflow.calls == [("run_single_point", True), ("close",)]


def test_submit_single_point_rejects_unconfirmed_real_mode():
    queue = TaskQueue()

    with pytest.raises(ConfigError, match="confirm_real"):
        asyncio.run(queue.submit_single_point("job-1", "config.yaml", None, "real"))

    assert queue._queue.empty()


def test_run_single_point_sync_rejects_unconfirmed_real_mode(monkeypatch):
    queue = TaskQueue()
    monkeypatch.setattr(task_queue_module, "load_workflow_and_devices", lambda *args, **kwargs: pytest.fail("loaded config"))

    with pytest.raises(ConfigError, match="confirm_real"):
        queue._run_single_point_sync("config.yaml", None, "real", False, "job-1")


class RealWorkflowStub:
    def __init__(self):
        self.calls = []

    def run_single_point(self, *, require_confirmation):
        self.calls.append(("run_single_point", require_confirmation))
        return "out"

    def close(self):
        self.calls.append(("close",))
