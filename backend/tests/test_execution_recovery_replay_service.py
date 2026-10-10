from datetime import datetime, timedelta, timezone

import pytest

from backend.session import (
    ExecutionRecoveryJournalEntry,
    ExecutionRecoveryReplayError as Error,
    ExecutionRecoveryReplayService,
)


def _entry(event_type, details, timestamp, session_id="session-1"):
    return ExecutionRecoveryJournalEntry(
        session_id=session_id,
        checkpoint_id="checkpoint-1",
        event_type=event_type,
        details=details,
        timestamp=timestamp,
    )


def _service(entries_by_session):
    return ExecutionRecoveryReplayService(
        journal_history_resolver=lambda session_id: tuple(entries_by_session.get(session_id, ())),
    )


class TestExecutionRecoveryReplayService:
    def test_create_execute_replay(self):
        base = datetime.now(timezone.utc)
        first = _entry("CHECKPOINT", {"step": 1}, base)
        second = _entry("VALIDATION", {"validated": True}, base + timedelta(seconds=1))
        replay_service = _service({"session-1": [first, second]})

        replay = replay_service.create("session-1")

        assert replay.session_id == "session-1"
        assert replay.journal_entry_ids == (first.entry_id, second.entry_id)
        assert replay.result is None

        executed = replay_service.execute(replay.replay_id)

        assert executed.result == {"step": 1, "validated": True}
        assert replay_service.result(replay.replay_id) == {"step": 1, "validated": True}

    def test_ordering(self):
        base = datetime.now(timezone.utc)
        first = _entry("CHECKPOINT", {"step": 1}, base)
        second = _entry("RETRY", {"step": 2}, base + timedelta(seconds=1))
        entries_by_session = {"session-1": [first, second]}
        replay_service = _service(entries_by_session)

        replay = replay_service.create("session-1")
        executed = replay_service.execute(replay.replay_id)

        assert executed.result == {"step": 2}

        reversed_entries_by_session = {"session-1": [second, first]}
        reversed_service = _service(reversed_entries_by_session)
        reversed_replay = reversed_service.create("session-1")
        reversed_executed = reversed_service.execute(reversed_replay.replay_id)

        assert reversed_executed.result == {"step": 1}

    def test_deterministic_result(self):
        base = datetime.now(timezone.utc)
        first = _entry("CHECKPOINT", {"step": 1}, base)
        entries_by_session = {"session-1": [first]}
        replay_service = _service(entries_by_session)
        replay = replay_service.create("session-1")

        first_execution = replay_service.execute(replay.replay_id)

        entries_by_session["session-1"].append(_entry("RETRY", {"step": 99}, base + timedelta(seconds=1)))

        second_execution = replay_service.execute(replay.replay_id)

        assert first_execution.result == second_execution.result == {"step": 1}

    def test_divergence_detection(self):
        base = datetime.now(timezone.utc)
        first = _entry("CHECKPOINT", {"step": 5, "flag": True}, base)
        replay_service = _service({"session-1": [first]})
        replay = replay_service.create("session-1")

        with pytest.raises(Error):
            replay_service.compare(replay.replay_id, {"step": 3})

        replay_service.execute(replay.replay_id)

        divergences = replay_service.compare(replay.replay_id, {"step": 3, "flag": True, "missing": "x"})

        assert {divergence["field"] for divergence in divergences} == {"step", "missing"}

        no_divergence = replay_service.compare(replay.replay_id, {"step": 5, "flag": True})
        assert no_divergence == ()

    def test_read_only_guarantee(self):
        base = datetime.now(timezone.utc)
        first = _entry("CHECKPOINT", {"step": 1}, base)
        entries_by_session = {"session-1": [first]}
        replay_service = _service(entries_by_session)

        replay = replay_service.create("session-1")
        executed = replay_service.execute(replay.replay_id)
        replay_service.compare(replay.replay_id, {"step": 1})

        assert entries_by_session["session-1"] == [first]
        assert first.details == {"step": 1}

        with pytest.raises(TypeError):
            executed.result["step"] = 2

    def test_unknown_replay_rejection(self):
        replay_service = _service({})

        with pytest.raises(Error):
            replay_service.execute("unknown-replay")

        with pytest.raises(Error):
            replay_service.compare("unknown-replay", {})

        with pytest.raises(Error):
            replay_service.result("unknown-replay")
