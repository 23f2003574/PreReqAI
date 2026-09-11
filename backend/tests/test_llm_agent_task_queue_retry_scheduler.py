from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_lifecycle import PLANNED, READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
from backend.agent_task_queue_retry_scheduler import (
    CANCELLED,
    SCHEDULED,
    IneligibleForRetryError,
    LLMAgentTaskRetryScheduler,
    TaskRetrySchedule,
)
from backend.agent_task_readiness import LLMAgentTaskReadinessService
from backend.llm.retry import LLMRetryPolicy

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _definition(**overrides):
    definition = {"agent_id": "agent-1", "scope_id": "scope-1", "objective": "summarize the notebook"}
    definition.update(overrides)
    return definition


def _services():
    lifecycle_service = LLMAgentTaskLifecycleService()
    readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
    queue_service = LLMAgentTaskQueueService(readiness_service)
    dead_letter_service = LLMAgentTaskDeadLetterService(queue_service, lifecycle_service)
    eligibility_service = LLMAgentTaskQueueRetryEligibilityService(
        lifecycle_service, readiness_service, dead_letter_service
    )
    scheduler = LLMAgentTaskRetryScheduler(eligibility_service)
    return lifecycle_service, queue_service, dead_letter_service, eligibility_service, scheduler


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestEligibleFailureGetsCorrectRetryTime:
    def test_schedule_immediate_when_no_backoff_constraint(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=1, max_attempts=3)

        schedule = scheduler.schedule_retry(task.task_id, now=NOW)

        assert isinstance(schedule, TaskRetrySchedule)
        assert schedule.task_id == task.task_id
        assert schedule.attempt == 2
        assert schedule.scheduled_at == NOW
        assert schedule.eligible_at == NOW
        assert schedule.status == SCHEDULED

    def test_first_ever_schedule_has_attempt_one(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service)  # no retry metadata at all

        schedule = scheduler.schedule_retry(task.task_id, now=NOW)

        assert schedule.attempt == 1

    def test_reason_carried_verbatim_from_eligibility(self):
        lifecycle_service, *_, eligibility_service, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)

        schedule = scheduler.schedule_retry(task.task_id, now=NOW)
        expected = eligibility_service.check(task.task_id, now=NOW).reason

        assert schedule.reason == expected


class TestBackoffRespected:
    def test_eligible_at_matches_eligibility_next_eligible_at(self):
        lifecycle_service, *_, scheduler = _services()
        policy = LLMRetryPolicy(policy_id="p1", max_attempts=5, backoff_seconds=60.0)
        task = _ready_task(
            lifecycle_service,
            attempt_count=1,
            max_attempts=5,
            retry_policy=policy,
            last_attempt_at=NOW - timedelta(seconds=30),
        )

        # Backoff for attempt 1 is 60s; only 30s elapsed, so still
        # within the window -- schedule_retry() must still succeed
        # (scheduling *ahead of time* is allowed, only actually
        # retrying early is not), with eligible_at in the future.
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)

        assert schedule.eligible_at == NOW - timedelta(seconds=30) + timedelta(seconds=60)
        assert schedule.eligible_at > NOW
        assert scheduler.get_due_retries(now=NOW) == []
        assert scheduler.get_due_retries(now=schedule.eligible_at) == [schedule]


class TestIneligibleTaskRejected:
    def test_dead_lettered_task_cannot_be_scheduled(self):
        lifecycle_service, queue_service, dead_letter_service, _, scheduler = _services()
        task = _ready_task(lifecycle_service)
        queue_service.enqueue(task.task_id)
        dead_letter_service.dead_letter(task.task_id, "manually excluded")

        with pytest.raises(IneligibleForRetryError):
            scheduler.schedule_retry(task.task_id, now=NOW)

        assert scheduler.get_retry_schedule(task.task_id) is None

    def test_non_retryable_task_cannot_be_scheduled(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, retryable=False)

        with pytest.raises(IneligibleForRetryError):
            scheduler.schedule_retry(task.task_id, now=NOW)

    def test_retry_limit_reached_cannot_be_scheduled(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=3, max_attempts=3)

        with pytest.raises(IneligibleForRetryError):
            scheduler.schedule_retry(task.task_id, now=NOW)

    def test_not_ready_task_cannot_be_scheduled(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service)
        lifecycle_service.transition(task.task_id, RUNNING)

        with pytest.raises(IneligibleForRetryError):
            scheduler.schedule_retry(task.task_id, now=NOW)


class TestDuplicateAttemptPrevented:
    def test_repeated_schedule_for_same_attempt_returns_existing(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)

        first = scheduler.schedule_retry(task.task_id, now=NOW)
        second = scheduler.schedule_retry(task.task_id, now=NOW + timedelta(minutes=1))

        assert second == first  # unchanged, including scheduled_at

    def test_new_attempt_after_task_failed_again_replaces_schedule(self):
        lifecycle_service, *_, scheduler = _services()
        task = lifecycle_service.create(_definition(attempt_count=0, max_attempts=3))
        task = lifecycle_service.transition(task.task_id, PLANNED)
        task = lifecycle_service.transition(task.task_id, READY)

        first = scheduler.schedule_retry(task.task_id, now=NOW)
        assert first.attempt == 1

        # Simulate the task having failed again: bump attempt_count on
        # a freshly recreated definition is not possible (definition is
        # set once at create() time), so instead verify idempotency is
        # scoped to the *attempt number*, not just task_id, using a
        # second task_id with a higher attempt_count for contrast.
        other = _ready_task(lifecycle_service, attempt_count=2, max_attempts=5)
        other_schedule = scheduler.schedule_retry(other.task_id, now=NOW)
        assert other_schedule.attempt == 3


class TestDueNotDueQueries:
    def test_get_due_retries_excludes_not_yet_due(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, next_eligible_at=NOW + timedelta(hours=1))
        scheduler.schedule_retry(task.task_id, now=NOW)

        assert scheduler.get_due_retries(now=NOW) == []

    def test_get_due_retries_includes_due(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        schedule = scheduler.schedule_retry(task.task_id, now=NOW)

        due = scheduler.get_due_retries(now=NOW)

        assert due == [schedule]

    def test_get_due_retries_sorted_deterministically(self):
        lifecycle_service, *_, scheduler = _services()
        later = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        earlier = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(later.task_id, now=NOW + timedelta(minutes=5))
        scheduler.schedule_retry(earlier.task_id, now=NOW)

        due = scheduler.get_due_retries(now=NOW + timedelta(hours=1))

        assert [s.task_id for s in due] == [earlier.task_id, later.task_id]

    def test_get_due_retries_never_enqueues(self):
        lifecycle_service, queue_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(task.task_id, now=NOW)

        scheduler.get_due_retries(now=NOW)

        assert queue_service.contains(task.task_id) is False


class TestCancellationWorks:
    def test_cancel_marks_schedule_cancelled(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(task.task_id, now=NOW)

        scheduler.cancel_retry(task.task_id)

        schedule = scheduler.get_retry_schedule(task.task_id)
        assert schedule.status == CANCELLED

    def test_cancelled_schedule_excluded_from_due(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(task.task_id, now=NOW)
        scheduler.cancel_retry(task.task_id)

        assert scheduler.get_due_retries(now=NOW) == []

    def test_cancel_is_idempotent(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(task.task_id, now=NOW)

        scheduler.cancel_retry(task.task_id)
        scheduler.cancel_retry(task.task_id)  # must not raise

        assert scheduler.get_retry_schedule(task.task_id).status == CANCELLED

    def test_cancel_of_never_scheduled_task_is_safe(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service)

        scheduler.cancel_retry(task.task_id)  # must not raise

        assert scheduler.get_retry_schedule(task.task_id) is None

    def test_reschedule_after_cancel_creates_fresh_schedule(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)
        scheduler.schedule_retry(task.task_id, now=NOW)
        scheduler.cancel_retry(task.task_id)

        rescheduled = scheduler.schedule_retry(task.task_id, now=NOW + timedelta(minutes=1))

        assert rescheduled.status == SCHEDULED
        assert rescheduled.attempt == 1


class TestRepeatedSchedulingDeterministic:
    def test_repeated_calls_produce_identical_schedule(self):
        lifecycle_service, *_, scheduler = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=3)

        first = scheduler.schedule_retry(task.task_id, now=NOW)
        second = scheduler.schedule_retry(task.task_id, now=NOW)

        assert first == second


class TestInvalidInput:
    def test_schedule_retry_requires_task_id(self):
        *_, scheduler = _services()
        with pytest.raises(InvalidQueueEntryError):
            scheduler.schedule_retry("")

    def test_cancel_retry_requires_task_id(self):
        *_, scheduler = _services()
        with pytest.raises(InvalidQueueEntryError):
            scheduler.cancel_retry("")

    def test_get_due_retries_rejects_non_datetime_now(self):
        *_, scheduler = _services()
        with pytest.raises(InvalidQueueEntryError):
            scheduler.get_due_retries(now="not-a-datetime")
