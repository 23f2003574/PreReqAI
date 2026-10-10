from datetime import (
    datetime,
    timedelta,
    timezone,
)

from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ExecutionBackpressureService,
    ExecutionDeadLetterService,
    ExecutionFairSchedulingService,
    ExecutionJob,
    ExecutionJobDependencyService,
    ExecutionJobQueueService,
    ExecutionResourceReservationService,
    ExecutionScheduleDecision,
    ExecutionSchedulerError as Error,
    ExecutionSchedulerFailoverService,
    ExecutionSchedulerService,
    ExecutionSchedulingReservationService,
    ExecutionSchedulingRetryPolicy,
    ExecutionSchedulingRetryService,
    ExecutionSchedulingWindowService,
)


class _FakeJobProvider:
    def __init__(self):
        self._jobs_by_scope = {}

    def queued(self, scope_id):
        return self._jobs_by_scope.get(scope_id, [])

    def set_queued(self, scope_id, jobs):
        self._jobs_by_scope[scope_id] = jobs


class _FakeAvailabilityService:
    def __init__(self):
        self._unavailable = set()

    def is_available(self, scheduler_id):
        return scheduler_id not in self._unavailable

    def mark_unavailable(self, scheduler_id):
        self._unavailable.add(scheduler_id)


SCOPE = "scope-1"
JOB = "job-1"
NOW = datetime.now(timezone.utc)


def _pipeline():
    queue_service = ExecutionJobQueueService()
    dependency_service = ExecutionJobDependencyService(queue_service)
    window_service = ExecutionSchedulingWindowService()
    backpressure_service = ExecutionBackpressureService()
    resource_reservation_service = ExecutionResourceReservationService({"gpu": 4})
    job_provider = _FakeJobProvider()
    fair_scheduling_service = ExecutionFairSchedulingService(job_provider)
    availability_service = _FakeAvailabilityService()
    failover_service = ExecutionSchedulerFailoverService(availability_service)
    scheduling_reservation_service = ExecutionSchedulingReservationService(queue_service)
    dead_letter_service = ExecutionDeadLetterService(retry_threshold=1)
    retry_service = ExecutionSchedulingRetryService(dead_letter_service)

    scheduler = ExecutionSchedulerService(
        queue_service=queue_service,
        dependency_service=dependency_service,
        window_service=window_service,
        backpressure_service=backpressure_service,
        resource_reservation_service=resource_reservation_service,
        fair_scheduling_service=fair_scheduling_service,
        failover_service=failover_service,
        scheduling_reservation_service=scheduling_reservation_service,
        retry_service=retry_service,
    )

    return SimpleNamespace(
        scheduler=scheduler,
        queue_service=queue_service,
        dependency_service=dependency_service,
        window_service=window_service,
        backpressure_service=backpressure_service,
        resource_reservation_service=resource_reservation_service,
        job_provider=job_provider,
        fair_scheduling_service=fair_scheduling_service,
        availability_service=availability_service,
        failover_service=failover_service,
        scheduling_reservation_service=scheduling_reservation_service,
        dead_letter_service=dead_letter_service,
        retry_service=retry_service,
    )


def _make_eligible(components, job_id=JOB, scope_id=SCOPE, schedulers=("scheduler-a",), create_window=True):
    components.queue_service.enqueue(ExecutionJob(job_id=job_id, session_id="session-1", payload=None))
    if create_window:
        components.window_service.create(scope_id, NOW - timedelta(hours=1), NOW + timedelta(hours=1))
    components.backpressure_service.configure(scope_id, 5)
    components.job_provider.set_queued(
        scope_id, [SimpleNamespace(job_id=job_id, priority="NORMAL", queued_at=NOW)]
    )
    components.failover_service.register(scope_id, list(schedulers))


class TestExecutionSchedulerService:
    def test_successful_scheduling(self):
        components = _pipeline()
        _make_eligible(components)

        result = components.scheduler.schedule(JOB, SCOPE)

        assert isinstance(result, ExecutionScheduleDecision)
        assert result.allowed is True
        assert result.scheduler_id == "scheduler-a"
        assert components.scheduler.decision(JOB) is result
        assert components.scheduling_reservation_service.active(JOB) is not None

    def test_dependency_blocking(self):
        components = _pipeline()
        _make_eligible(components)
        components.queue_service.enqueue(ExecutionJob(job_id="blocker", session_id="session-1", payload=None))
        components.dependency_service.add(JOB, "blocker")

        result = components.scheduler.schedule(JOB, SCOPE)

        assert result.allowed is False
        assert "dependenc" in result.reason.lower()
        assert result.scheduler_id is None

    def test_capacity_blocking(self):
        components = _pipeline()
        _make_eligible(components)
        components.backpressure_service.configure(SCOPE, 1)
        components.backpressure_service.record_enqueue(SCOPE)

        result = components.scheduler.schedule(JOB, SCOPE)

        assert result.allowed is False
        assert "backpressure" in result.reason.lower() or "saturat" in result.reason.lower()

    def test_scheduling_window_blocking(self):
        components = _pipeline()
        _make_eligible(components, create_window=False)

        result = components.scheduler.schedule(JOB, SCOPE)

        assert result.allowed is False
        assert "window" in result.reason.lower()

    def test_retry_path(self):
        components = _pipeline()
        _make_eligible(components)
        components.retry_service.configure(
            SCOPE, ExecutionSchedulingRetryPolicy(policy_id="p1", max_attempts=1, backoff_seconds=1)
        )
        components.queue_service.enqueue(ExecutionJob(job_id="blocker", session_id="session-1", payload=None))
        components.dependency_service.add(JOB, "blocker")

        first = components.scheduler.schedule(JOB, SCOPE)
        second = components.scheduler.schedule(JOB, SCOPE)
        third = components.scheduler.schedule(JOB, SCOPE)

        assert first.allowed is False
        assert second.allowed is False
        assert third.allowed is False
        assert components.dead_letter_service.list(JOB) != ()

    def test_scheduler_failover(self):
        components = _pipeline()
        _make_eligible(components, schedulers=("scheduler-a", "scheduler-b"))
        components.availability_service.mark_unavailable("scheduler-a")

        result = components.scheduler.schedule(JOB, SCOPE)

        assert result.allowed is True
        assert result.scheduler_id == "scheduler-b"

    def test_all_schedulers_unavailable_blocks_scheduling(self):
        components = _pipeline()
        _make_eligible(components, schedulers=("scheduler-a",))
        components.availability_service.mark_unavailable("scheduler-a")

        result = components.scheduler.schedule(JOB, SCOPE)

        assert result.allowed is False
        assert "scheduler" in result.reason.lower()

    def test_deterministic_decision(self):
        components = _pipeline()
        _make_eligible(components, create_window=False)

        first = components.scheduler.schedule(JOB, SCOPE)
        second = components.scheduler.schedule(JOB, SCOPE)

        assert first.allowed is False
        assert second.allowed is False
        assert first.reason == second.reason
        assert components.scheduler.decision(JOB) is second

    def test_evaluate_has_no_side_effects(self):
        components = _pipeline()
        _make_eligible(components)

        result = components.scheduler.evaluate(JOB, SCOPE)

        assert result.allowed is True
        assert components.scheduling_reservation_service.active(JOB) is None

        with pytest.raises(Error):
            components.scheduler.decision(JOB)

    def test_cancel_releases_reservation_and_cancels_job(self):
        components = _pipeline()
        _make_eligible(components)
        components.scheduler.schedule(JOB, SCOPE)

        components.scheduler.cancel(JOB)

        assert components.scheduling_reservation_service.active(JOB) is None
        assert components.queue_service.status(JOB) == "CANCELLED"

    def test_decision_lookup_without_prior_schedule_is_rejected(self):
        components = _pipeline()

        with pytest.raises(Error):
            components.scheduler.decision("does-not-exist")

    def test_scheduling_unknown_job_is_rejected(self):
        components = _pipeline()

        with pytest.raises(Error):
            components.scheduler.schedule("does-not-exist", SCOPE)
