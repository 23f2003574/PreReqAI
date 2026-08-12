from datetime import (
    datetime,
)

from threading import (
    RLock,
)

from .execution_recovery_journal_entry_error import (
    ExecutionRecoveryJournalEntryError,
)

from .execution_recovery_journal_entry import (
    SUPPORTED_EVENT_TYPES,
    ExecutionRecoveryJournalEntry,
)


class ExecutionRecoveryJournalService:
    """
    Append-only log of every recovery decision and state transition,
    kept for debugging and replay.

    Entries are caller-constructed ExecutionRecoveryJournalEntry
    instances; this service only appends, lists, filters, and purges
    them. It never alters the recovery state described by an entry,
    and never edits or removes an individual entry once recorded.

    Behavior:
    - record() appends an entry; an entry_id may only be recorded
      once
    - history() lists a session's entries in chronological order
    - latest() returns a session's most recent entry, or None
    - filter() narrows history() to one event type
    - purge() permanently removes every entry, across all sessions,
      timestamped before a given cutoff, and reports how many were
      removed

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._entries_by_id = {}
        self._entry_ids_by_session = {}
        self._lock = RLock()

    def record(self, event: ExecutionRecoveryJournalEntry) -> ExecutionRecoveryJournalEntry:
        """
        Append an entry to the journal.

        Raises:
            ExecutionRecoveryJournalEntryError: If event is not an
                ExecutionRecoveryJournalEntry, or its entry_id has
                already been recorded
        """

        if not isinstance(event, ExecutionRecoveryJournalEntry):
            raise ExecutionRecoveryJournalEntryError(
                "Cannot record an event that is not an ExecutionRecoveryJournalEntry."
            )

        with self._lock:
            if event.entry_id in self._entries_by_id:
                raise ExecutionRecoveryJournalEntryError(f"Entry ID {event.entry_id!r} has already been recorded.")

            self._entries_by_id[event.entry_id] = event
            self._entry_ids_by_session.setdefault(event.session_id, []).append(event.entry_id)

            return event

    def history(self, session_id: str) -> tuple:
        """
        List a session's entries in chronological order.

        Raises:
            ExecutionRecoveryJournalEntryError: If session_id is
                None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            entries = [self._entries_by_id[entry_id] for entry_id in self._entry_ids_by_session.get(session_id, [])]

            return tuple(sorted(entries, key=lambda entry: (entry.timestamp, entry.entry_id)))

    def latest(self, session_id: str) -> ExecutionRecoveryJournalEntry | None:
        """
        Return a session's most recent entry.

        Raises:
            ExecutionRecoveryJournalEntryError: If session_id is
                None or blank
        """

        history = self.history(session_id)

        return history[-1] if history else None

    def filter(self, session_id: str, event_type: str) -> tuple:
        """
        Narrow a session's history to one event type.

        Raises:
            ExecutionRecoveryJournalEntryError: If session_id or
                event_type is None or blank, or event_type is
                unsupported
        """

        self._validate_id(event_type, "event type")

        if event_type not in SUPPORTED_EVENT_TYPES:
            raise ExecutionRecoveryJournalEntryError(
                f"Unsupported event type {event_type!r}: expected one of {sorted(SUPPORTED_EVENT_TYPES)}."
            )

        return tuple(entry for entry in self.history(session_id) if entry.event_type == event_type)

    def purge(self, before_timestamp: datetime) -> int:
        """
        Permanently remove every entry, across all sessions,
        timestamped before a cutoff.

        Raises:
            ExecutionRecoveryJournalEntryError: If before_timestamp
                is not a datetime
        """

        if not isinstance(before_timestamp, datetime):
            raise ExecutionRecoveryJournalEntryError("Cannot purge with a non-datetime before_timestamp.")

        with self._lock:
            purge_ids = [
                entry_id for entry_id, entry in self._entries_by_id.items() if entry.timestamp < before_timestamp
            ]

            for entry_id in purge_ids:
                entry = self._entries_by_id.pop(entry_id)

                session_entry_ids = self._entry_ids_by_session.get(entry.session_id)

                if session_entry_ids is not None:
                    session_entry_ids.remove(entry_id)

                    if not session_entry_ids:
                        del self._entry_ids_by_session[entry.session_id]

            return len(purge_ids)

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryJournalEntryError(f"Cannot use an empty or blank {field_name}.")
