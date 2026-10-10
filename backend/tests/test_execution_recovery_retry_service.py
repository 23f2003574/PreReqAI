import pytest

from backend.session import (
    ExecutionRecoveryAttemptError as Error,
    ExecutionRecoveryRetryService,
)


class TestExecutionRecoveryRetryService:
    def test_start_attempt(self):
        retry_service = ExecutionRecoveryRetryService()

        attempt = retry_service.start("plan-1")

        assert attempt.plan_id == "plan-1"
        assert attempt.attempt_number == 1
        assert attempt.status == "IN_PROGRESS"
        assert attempt.started_at is not None
        assert attempt.finished_at is None

    def test_finish_success_and_failure(self):
        retry_service = ExecutionRecoveryRetryService()

        failed_attempt = retry_service.start("plan-1")
        finished = retry_service.finish(failed_attempt.attempt_id, "FAILED")

        assert finished.status == "FAILED"
        assert finished.finished_at is not None

        with pytest.raises(Error):
            retry_service.finish(failed_attempt.attempt_id, "SUCCEEDED")

        succeeded_attempt = retry_service.start("plan-2")
        finished_success = retry_service.finish(succeeded_attempt.attempt_id, "SUCCEEDED")

        assert finished_success.status == "SUCCEEDED"

    def test_retry_failed_plan(self):
        retry_service = ExecutionRecoveryRetryService()
        first = retry_service.start("plan-1")
        retry_service.finish(first.attempt_id, "FAILED")

        retried = retry_service.retry("plan-1")

        assert retried.plan_id == "plan-1"
        assert retried.attempt_number == 2
        assert retried.status == "IN_PROGRESS"

    def test_retry_successful_plan_rejected(self):
        retry_service = ExecutionRecoveryRetryService()
        attempt = retry_service.start("plan-1")
        retry_service.finish(attempt.attempt_id, "SUCCEEDED")

        with pytest.raises(Error):
            retry_service.retry("plan-1")

        with pytest.raises(Error):
            retry_service.start("plan-1")

    def test_attempt_ordering(self):
        retry_service = ExecutionRecoveryRetryService()
        first = retry_service.start("plan-1")
        retry_service.finish(first.attempt_id, "FAILED")
        second = retry_service.retry("plan-1")
        retry_service.finish(second.attempt_id, "FAILED")
        third = retry_service.retry("plan-1")

        history = retry_service.attempts("plan-1")

        assert [attempt.attempt_number for attempt in history] == [1, 2, 3]
        assert history[-1] == third
        assert retry_service.latest("plan-1") == third

    def test_duplicate_attempt_prevention(self):
        retry_service = ExecutionRecoveryRetryService()
        retry_service.start("plan-1")

        with pytest.raises(Error):
            retry_service.start("plan-1")

        with pytest.raises(Error):
            retry_service.retry("plan-1")
