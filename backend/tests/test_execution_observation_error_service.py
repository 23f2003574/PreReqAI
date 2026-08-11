from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionObservationErrorError as Error,
    ExecutionObservationError,
    ExecutionObservationErrorService,
)


def _error(
    session_id="session-1",
    stage_id=None,
    error_type="TIMEOUT",
    message="request timed out",
    error_id=None,
    timestamp=None,
):
    kwargs = dict(
        session_id=session_id,
        stage_id=stage_id,
        error_type=error_type,
        message=message,
    )

    if error_id is not None:
        kwargs["error_id"] = error_id

    if timestamp is not None:
        kwargs["timestamp"] = timestamp

    return ExecutionObservationError(**kwargs)


class TestExecutionObservationErrorService:
    def test_record_error(self):
        error_service = ExecutionObservationErrorService()
        error = _error()

        recorded = error_service.record(error)

        assert recorded == error
        assert recorded.message == "request timed out"
        assert error_service.history("session-1") == [error]

    def test_session_history(self):
        error_service = ExecutionObservationErrorService()
        base = datetime.now(timezone.utc)
        first = _error(error_id="error-1", timestamp=base)
        second = _error(error_id="error-2", timestamp=base + timedelta(seconds=1))
        # Record out of chronological order to prove history() sorts by timestamp.
        error_service.record(second)
        error_service.record(first)

        history = error_service.history("session-1")

        assert [error.error_id for error in history] == ["error-1", "error-2"]

    def test_stage_filtering(self):
        error_service = ExecutionObservationErrorService()
        with_stage = _error(error_id="error-1", stage_id="stage-1")
        other_stage = _error(error_id="error-2", stage_id="stage-2")
        no_stage = _error(error_id="error-3", stage_id=None)
        error_service.record(with_stage)
        error_service.record(other_stage)
        error_service.record(no_stage)

        stage_errors = error_service.stage_errors("session-1", "stage-1")

        assert stage_errors == [with_stage]

    def test_latest_error(self):
        error_service = ExecutionObservationErrorService()
        base = datetime.now(timezone.utc)
        first = _error(error_id="error-1", timestamp=base)
        second = _error(error_id="error-2", timestamp=base + timedelta(seconds=1))
        error_service.record(first)
        error_service.record(second)

        assert error_service.latest("session-1") == second

        with pytest.raises(Error):
            error_service.latest("unknown-session")

    def test_error_count(self):
        error_service = ExecutionObservationErrorService()

        assert error_service.count("session-1") == 0

        error_service.record(_error(error_id="error-1"))
        error_service.record(_error(error_id="error-2"))

        assert error_service.count("session-1") == 2

    def test_duplicate_id_rejection(self):
        error_service = ExecutionObservationErrorService()
        error = _error(error_id="error-1")
        error_service.record(error)

        duplicate = _error(error_id="error-1", message="a different message")

        with pytest.raises(Error):
            error_service.record(duplicate)

    def test_rejects_invalid_error(self):
        error_service = ExecutionObservationErrorService()

        with pytest.raises(Error):
            error_service.record("not-an-error")
