from datetime import datetime, timedelta, timezone

import pytest

from backend.session import (
    ExecutionRecoveryJournalEntry,
    ExecutionRecoveryJournalEntryError as Error,
    ExecutionRecoveryJournalService,
)


def _entry(session_id="session-1", checkpoint_id="checkpoint-1", event_type="CHECKPOINT", **kwargs):
    return ExecutionRecoveryJournalEntry(
        session_id=session_id, checkpoint_id=checkpoint_id, event_type=event_type, **kwargs
    )


class TestExecutionRecoveryJournalService:
    def test_record_event(self):
        journal_service = ExecutionRecoveryJournalService()
        entry = _entry(details={"note": "created"})

        recorded = journal_service.record(entry)

        assert recorded == entry
        assert journal_service.history("session-1") == (entry,)

        with pytest.raises(Error):
            journal_service.record("not-an-entry")

    def test_history_ordering(self):
        journal_service = ExecutionRecoveryJournalService()
        base = datetime.now(timezone.utc)
        first = _entry(event_type="CHECKPOINT", timestamp=base)
        second = _entry(event_type="VALIDATION", timestamp=base + timedelta(seconds=1))
        third = _entry(event_type="CONFLICT", timestamp=base + timedelta(seconds=2))

        journal_service.record(third)
        journal_service.record(first)
        journal_service.record(second)

        assert journal_service.history("session-1") == (first, second, third)

    def test_event_filtering(self):
        journal_service = ExecutionRecoveryJournalService()
        checkpoint_event = _entry(event_type="CHECKPOINT")
        retry_event = _entry(event_type="RETRY")
        other_session_retry = _entry(session_id="session-2", event_type="RETRY")

        for event in (checkpoint_event, retry_event, other_session_retry):
            journal_service.record(event)

        assert journal_service.filter("session-1", "RETRY") == (retry_event,)
        assert journal_service.filter("session-1", "CHECKPOINT") == (checkpoint_event,)
        assert journal_service.filter("session-1", "ROLLBACK") == ()

        with pytest.raises(Error):
            journal_service.filter("session-1", "NOT_A_TYPE")

    def test_latest_entry(self):
        journal_service = ExecutionRecoveryJournalService()
        base = datetime.now(timezone.utc)
        first = _entry(event_type="CHECKPOINT", timestamp=base)
        second = _entry(event_type="VALIDATION", timestamp=base + timedelta(seconds=1))

        journal_service.record(first)
        journal_service.record(second)

        assert journal_service.latest("session-1") == second
        assert journal_service.latest("unknown-session") is None

    def test_purge(self):
        journal_service = ExecutionRecoveryJournalService()
        base = datetime.now(timezone.utc)
        old_entry = _entry(session_id="session-1", timestamp=base - timedelta(days=2))
        other_old_entry = _entry(session_id="session-2", timestamp=base - timedelta(days=1))
        recent_entry = _entry(session_id="session-1", timestamp=base)

        for event in (old_entry, other_old_entry, recent_entry):
            journal_service.record(event)

        purged_count = journal_service.purge(base - timedelta(hours=1))

        assert purged_count == 2
        assert journal_service.history("session-1") == (recent_entry,)
        assert journal_service.history("session-2") == ()

        with pytest.raises(Error):
            journal_service.purge("not-a-datetime")

    def test_duplicate_id_rejection(self):
        journal_service = ExecutionRecoveryJournalService()
        entry = _entry(entry_id="fixed-id")
        journal_service.record(entry)

        duplicate = _entry(entry_id="fixed-id", event_type="ROLLBACK")

        with pytest.raises(Error):
            journal_service.record(duplicate)

        with pytest.raises(Error):
            journal_service.record(entry)
