from collections.abc import (
    Mapping,
)

from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from types import (
    MappingProxyType,
)

from uuid import uuid4

from .execution_recovery_journal_entry_error import (
    ExecutionRecoveryJournalEntryError,
)

SUPPORTED_EVENT_TYPES = frozenset(
    {
        "CHECKPOINT",
        "VALIDATION",
        "CONFLICT",
        "RETRY",
        "ROLLBACK",
    }
)


@dataclass(frozen=True)
class ExecutionRecoveryJournalEntry:
    """
    Immutable record of one recovery decision or state transition,
    kept for debugging and replay.

    The entry is a value object only. It performs no recording of
    its own; appending an entry, listing a session's history,
    filtering by event type, and purging old entries is the
    responsibility of an execution recovery journal service.

    Attributes:
        entry_id: The entry's unique identifier
        session_id: The identifier of the execution session the
            entry belongs to
        checkpoint_id: The identifier of the checkpoint the entry
            relates to
        event_type: The kind of event recorded, one of CHECKPOINT,
            VALIDATION, CONFLICT, RETRY, or ROLLBACK
        details: Freeform, event-specific detail, as an immutable
            mapping
        timestamp: When the recorded event occurred
    """

    session_id: str

    checkpoint_id: str

    event_type: str

    details: Mapping = field(
        default_factory=dict,
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    entry_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.entry_id, "entry ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.checkpoint_id, "checkpoint ID")
        self._require_text(self.event_type, "event type")

        if self.event_type not in SUPPORTED_EVENT_TYPES:
            raise ExecutionRecoveryJournalEntryError(
                f"Unsupported event type {self.event_type!r}: expected one of {sorted(SUPPORTED_EVENT_TYPES)}."
            )

        if not isinstance(self.timestamp, datetime):
            raise ExecutionRecoveryJournalEntryError(
                "Cannot build an execution recovery journal entry with a non-datetime timestamp."
            )

        if not isinstance(self.details, Mapping):
            raise ExecutionRecoveryJournalEntryError(
                "Cannot build an execution recovery journal entry with a non-mapping details."
            )

        object.__setattr__(self, "details", MappingProxyType(dict(self.details)))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryJournalEntryError(
                f"Cannot build an execution recovery journal entry with an empty or blank {field_name}."
            )
