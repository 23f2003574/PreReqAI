import pytest

from backend.session import (
    ExecutionObservationHealthTransitionError as Error,
    ExecutionObservationHealthHistoryService,
)


class TestExecutionObservationHealthHistoryService:
    def test_record_transition(self):
        history_service = ExecutionObservationHealthHistoryService()

        transition = history_service.record("session-1", "HEALTHY", "DEGRADED", reasons=("an error occurred",))

        assert transition.session_id == "session-1"
        assert transition.previous_status == "HEALTHY"
        assert transition.current_status == "DEGRADED"
        assert transition.reasons == ("an error occurred",)
        assert history_service.history("session-1") == [transition]

    def test_unchanged_status_ignored(self):
        history_service = ExecutionObservationHealthHistoryService()

        result = history_service.record("session-1", "HEALTHY", "HEALTHY")

        assert result is None
        assert history_service.history("session-1") == []

    def test_history_ordering(self):
        history_service = ExecutionObservationHealthHistoryService()

        first = history_service.record("session-1", "HEALTHY", "DEGRADED")
        second = history_service.record("session-1", "DEGRADED", "UNHEALTHY")
        third = history_service.record("session-1", "UNHEALTHY", "HEALTHY")

        history = history_service.history("session-1")

        assert history == [first, second, third]

    def test_latest_transition(self):
        history_service = ExecutionObservationHealthHistoryService()
        history_service.record("session-1", "HEALTHY", "DEGRADED")
        second = history_service.record("session-1", "DEGRADED", "UNHEALTHY")

        assert history_service.latest("session-1") == second

        with pytest.raises(Error):
            history_service.latest("unknown-session")

    def test_status_filtering(self):
        history_service = ExecutionObservationHealthHistoryService()
        matching_1 = history_service.record("session-1", "HEALTHY", "DEGRADED")
        matching_2 = history_service.record("session-2", "HEALTHY", "DEGRADED")
        history_service.record("session-1", "DEGRADED", "UNHEALTHY")

        matching = history_service.transitions("HEALTHY", "DEGRADED")

        assert matching == [matching_1, matching_2]

    def test_duplicate_id_rejection(self):
        history_service = ExecutionObservationHealthHistoryService()
        history_service.record("session-1", "HEALTHY", "DEGRADED", transition_id="transition-1")

        with pytest.raises(Error):
            history_service.record("session-1", "DEGRADED", "UNHEALTHY", transition_id="transition-1")
