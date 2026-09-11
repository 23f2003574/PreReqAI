from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_task_lifecycle import PLANNED, READY, RUNNING, LLMAgentTaskLifecycleService
from backend.agent_task_queue import InvalidQueueEntryError, LLMAgentTaskQueueService
from backend.agent_task_queue_dead_letter import LLMAgentTaskDeadLetterService
from backend.agent_task_queue_retry_eligibility import LLMAgentTaskQueueRetryEligibilityService
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
    return lifecycle_service, queue_service, dead_letter_service, eligibility_service


def _ready_task(lifecycle_service, **overrides):
    task = lifecycle_service.create(_definition(**overrides))
    task = lifecycle_service.transition(task.task_id, PLANNED)
    task = lifecycle_service.transition(task.task_id, READY)
    return task


class TestRetryableFailureEligible:
    def test_retryable_task_within_limit_is_eligible(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service, retryable=True, attempt_count=1, max_attempts=3)

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is True
        assert result.attempt_count == 1
        assert result.remaining_attempts == 2
        assert result.dead_letter_required is False

    def test_no_retry_metadata_recorded_is_reported_explicitly(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service)

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is True
        assert result.attempt_count is None
        assert result.remaining_attempts is None
        assert result.next_eligible_at is None


class TestRetryLimitReached:
    def test_attempt_count_at_max_is_ineligible(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=3, max_attempts=3)

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is False
        assert result.remaining_attempts == 0
        assert result.dead_letter_required is True
        assert "retry limit" in result.reason

    def test_attempt_count_past_max_is_ineligible(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=5, max_attempts=3)

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is False
        assert result.remaining_attempts == 0


class TestNonRetryableFailure:
    def test_explicit_non_retryable_marker_is_ineligible(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service, retryable=False, attempt_count=0, max_attempts=3)

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is False
        assert "not retryable" in result.reason
        assert result.dead_letter_required is True

    def test_failure_service_permanent_classification_is_ineligible(self):
        lifecycle_service, queue_service, dead_letter_service, _ = _services()

        @dataclass
        class _Classification:
            category: str
            reason: str

        class _FakeFailureService:
            def classify(self, execution_id, step_id):
                return _Classification(category="PERMANENT", reason="unrecoverable error")

        readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
        eligibility_service = LLMAgentTaskQueueRetryEligibilityService(
            lifecycle_service, readiness_service, dead_letter_service, failure_service=_FakeFailureService()
        )
        task = _ready_task(lifecycle_service, execution_id="exec-1", step_id="step-1")

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is False
        assert "PERMANENT" in result.reason

    def test_failure_service_retryable_classification_is_eligible(self):
        lifecycle_service, queue_service, dead_letter_service, _ = _services()

        @dataclass
        class _Classification:
            category: str
            reason: str

        class _FakeFailureService:
            def classify(self, execution_id, step_id):
                return _Classification(category="RETRYABLE", reason="timed out")

        readiness_service = LLMAgentTaskReadinessService(lifecycle_service)
        eligibility_service = LLMAgentTaskQueueRetryEligibilityService(
            lifecycle_service, readiness_service, dead_letter_service, failure_service=_FakeFailureService()
        )
        task = _ready_task(lifecycle_service, execution_id="exec-1", step_id="step-1")

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is True


class TestBackoffWindow:
    def test_backoff_not_elapsed_is_ineligible(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service, next_eligible_at=NOW + timedelta(minutes=5))

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is False
        assert "backoff window" in result.reason
        assert result.next_eligible_at == NOW + timedelta(minutes=5)

    def test_backoff_elapsed_is_eligible(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service, next_eligible_at=NOW - timedelta(seconds=1))

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is True

    def test_backoff_derived_from_policy_and_last_attempt(self):
        lifecycle_service, _, _, eligibility_service = _services()
        policy = LLMRetryPolicy(policy_id="p1", max_attempts=5, backoff_seconds=60.0)
        task = _ready_task(
            lifecycle_service,
            attempt_count=1,
            max_attempts=5,
            retry_policy=policy,
            last_attempt_at=NOW - timedelta(seconds=30),
        )

        # compute_backoff(policy, 1) == 60 * 2**0 == 60s; only 30s have
        # passed, so still within the backoff window.
        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is False
        assert result.next_eligible_at == NOW - timedelta(seconds=30) + timedelta(seconds=60)


class TestDeadLetteredTaskIneligible:
    def test_dead_lettered_task_is_ineligible_regardless_of_attempts(self):
        lifecycle_service, queue_service, dead_letter_service, eligibility_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=5)
        queue_service.enqueue(task.task_id)
        dead_letter_service.dead_letter(task.task_id, "manually excluded")

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is False
        assert "dead-lettered" in result.reason
        assert result.dead_letter_required is False  # already dead-lettered, no need to recommend it again


class TestNotReadyTaskIneligible:
    def test_not_ready_task_is_ineligible(self):
        lifecycle_service, queue_service, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service, attempt_count=0, max_attempts=5)
        lifecycle_service.transition(task.task_id, RUNNING)  # no longer permits entering RUNNING again

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is False


class TestBoundaryTimestamps:
    def test_now_exactly_at_next_eligible_at_is_eligible(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service, next_eligible_at=NOW)

        result = eligibility_service.check(task.task_id, now=NOW)

        assert result.eligible is True

    def test_now_one_microsecond_before_is_ineligible(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service, next_eligible_at=NOW)

        result = eligibility_service.check(task.task_id, now=NOW - timedelta(microseconds=1))

        assert result.eligible is False

    def test_check_is_deterministic_for_same_now(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service, next_eligible_at=NOW + timedelta(minutes=1))

        first = eligibility_service.check(task.task_id, now=NOW)
        second = eligibility_service.check(task.task_id, now=NOW)

        assert first == second


class TestInvalidInput:
    def test_check_requires_task_id(self):
        _, _, _, eligibility_service = _services()
        with pytest.raises(InvalidQueueEntryError):
            eligibility_service.check("")

    def test_check_rejects_non_datetime_now(self):
        lifecycle_service, _, _, eligibility_service = _services()
        task = _ready_task(lifecycle_service)
        with pytest.raises(InvalidQueueEntryError):
            eligibility_service.check(task.task_id, now="not-a-datetime")

    def test_check_unknown_task_is_ineligible_not_raised(self):
        _, _, _, eligibility_service = _services()
        result = eligibility_service.check("no-such-task", now=NOW)
        assert result.eligible is False
