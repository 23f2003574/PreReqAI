from datetime import (
    datetime,
    timezone,
)

from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ExecutionSchedulingRetryError as Error,
    ExecutionSchedulingRetryPolicy,
    ExecutionSchedulingRetryService,
)


class _FakeDeadLetterService:
    def __init__(self):
        self.moved = []

    def move(self, job_id, reason):
        self.moved.append((job_id, reason))
        return SimpleNamespace(job_id=job_id, reason=reason)


def _build():
    dead_letter_service = _FakeDeadLetterService()
    return dead_letter_service, ExecutionSchedulingRetryService(dead_letter_service)


def _policy(max_attempts=3, backoff_seconds=1, enabled=True):
    return ExecutionSchedulingRetryPolicy(
        policy_id="policy-1",
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
        enabled=enabled,
    )


class TestExecutionSchedulingRetryService:
    def test_configure_policy(self):
        _, service = _build()

        configured = service.configure("scope-1", _policy())

        assert isinstance(configured, ExecutionSchedulingRetryPolicy)
        assert configured.policy_id == "policy-1"

    def test_configure_with_non_policy_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.configure("scope-1", object())

    def test_retry_scheduling(self):
        _, service = _build()
        service.configure("scope-1", _policy(max_attempts=3, backoff_seconds=1))

        next_retry_at = service.retry("job-1", "scope-1")

        assert isinstance(next_retry_at, datetime)
        assert next_retry_at > datetime.now(timezone.utc)
        assert service.attempts("job-1") == 1
        assert service.next_retry("job-1") == next_retry_at

    def test_backoff_calculation(self):
        _, service = _build()
        service.configure("scope-1", _policy(max_attempts=5, backoff_seconds=1))

        first = service.retry("job-1", "scope-1")
        second = service.retry("job-1", "scope-1")
        third = service.retry("job-1", "scope-1")

        first_delay = (first - datetime.now(timezone.utc)).total_seconds()
        second_delay = (second - datetime.now(timezone.utc)).total_seconds()
        third_delay = (third - datetime.now(timezone.utc)).total_seconds()

        assert 0.9 < first_delay < 1.1
        assert 1.9 < second_delay < 2.1
        assert 3.9 < third_delay < 4.1

    def test_max_attempt_enforcement_and_dead_letter_handoff(self):
        dead_letter_service, service = _build()
        service.configure("scope-1", _policy(max_attempts=2, backoff_seconds=1))

        service.retry("job-1", "scope-1")
        service.retry("job-1", "scope-1")
        result = service.retry("job-1", "scope-1")

        assert result is None
        assert dead_letter_service.moved == [("job-1", "max scheduling retry attempts exceeded")]
        assert service.next_retry("job-1") is None
        assert service.attempts("job-1") == 2

    def test_retry_after_dead_letter_handoff_is_rejected(self):
        _, service = _build()
        service.configure("scope-1", _policy(max_attempts=1, backoff_seconds=1))
        service.retry("job-1", "scope-1")
        service.retry("job-1", "scope-1")

        with pytest.raises(Error):
            service.retry("job-1", "scope-1")

    def test_disabled_policy_rejects_retry(self):
        _, service = _build()
        service.configure("scope-1", _policy(enabled=False))

        with pytest.raises(Error):
            service.retry("job-1", "scope-1")

    def test_retry_on_unconfigured_scope_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.retry("job-1", "scope-1")

    def test_next_retry_on_unknown_job_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.next_retry("does-not-exist")

    def test_attempts_on_unknown_job_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.attempts("does-not-exist")
