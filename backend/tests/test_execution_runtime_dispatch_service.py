import pytest

from backend.session import (
    ExecutionRuntimeDispatch,
    ExecutionRuntimeDispatchError as Error,
    ExecutionRuntimeDispatchService,
)


class _FakeDecision:
    def __init__(self, allowed, scheduler_id=None):
        self.allowed = allowed
        self.scheduler_id = scheduler_id


class _FakeSchedulerService:
    def __init__(self, decisions_by_job=None):
        self._decisions_by_job = dict(decisions_by_job or {})

    def decision(self, job_id):
        if job_id not in self._decisions_by_job:
            raise ValueError(f"unknown job {job_id!r}")

        return self._decisions_by_job[job_id]


def _build(decisions_by_job=None):
    scheduler_service = _FakeSchedulerService(
        decisions_by_job
        or {
            "job-1": _FakeDecision(True, "scheduler-a"),
            "job-2": _FakeDecision(True, "scheduler-b"),
        }
    )
    return scheduler_service, ExecutionRuntimeDispatchService(scheduler_service)


class TestExecutionRuntimeDispatchService:
    def test_dispatch_job(self):
        _, service = _build()

        dispatch = service.dispatch("job-1")

        assert isinstance(dispatch, ExecutionRuntimeDispatch)
        assert dispatch.job_id == "job-1"
        assert dispatch.scheduler_id == "scheduler-a"
        assert dispatch.target == "scheduler-a"
        assert dispatch.status == "DISPATCHED"

    def test_duplicate_dispatch_is_rejected(self):
        _, service = _build()
        service.dispatch("job-1")

        with pytest.raises(Error):
            service.dispatch("job-1")

    def test_status_lookup(self):
        _, service = _build()
        dispatch = service.dispatch("job-1")

        assert service.status(dispatch.dispatch_id) == "DISPATCHED"

    def test_cancellation(self):
        _, service = _build()
        dispatch = service.dispatch("job-1")

        cancelled = service.cancel(dispatch.dispatch_id)

        assert cancelled.status == "CANCELLED"
        assert service.status(dispatch.dispatch_id) == "CANCELLED"

    def test_cancellation_is_idempotent(self):
        _, service = _build()
        dispatch = service.dispatch("job-1")
        service.cancel(dispatch.dispatch_id)

        second = service.cancel(dispatch.dispatch_id)

        assert second.status == "CANCELLED"

    def test_cancelled_dispatch_cannot_start_again(self):
        _, service = _build()
        dispatch = service.dispatch("job-1")
        service.cancel(dispatch.dispatch_id)

        redispatched = service.dispatch("job-1")

        assert redispatched.dispatch_id != dispatch.dispatch_id
        assert redispatched.status == "DISPATCHED"

    def test_active_lookup(self):
        _, service = _build()
        dispatch = service.dispatch("job-1")

        active = service.active("scheduler-a")

        assert len(active) == 1
        assert active[0].dispatch_id == dispatch.dispatch_id

        service.cancel(dispatch.dispatch_id)

        assert service.active("scheduler-a") == ()

    def test_unschedulable_job_is_rejected(self):
        _, service = _build(decisions_by_job={"job-1": _FakeDecision(False)})

        with pytest.raises(Error):
            service.dispatch("job-1")

    def test_dispatching_unknown_job_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.dispatch("does-not-exist")

    def test_status_lookup_for_unknown_dispatch_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.status("does-not-exist")

    def test_cancelling_unknown_dispatch_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.cancel("does-not-exist")
