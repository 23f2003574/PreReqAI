from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_storage_garbage_record_error import (
    ExecutionStorageGarbageRecordError,
)

RESOURCE_VOLUME = "VOLUME"

RESOURCE_SNAPSHOT = "SNAPSHOT"

RESOURCE_REPLICA = "REPLICA"

RESOURCE_TYPES = (
    RESOURCE_VOLUME,
    RESOURCE_SNAPSHOT,
    RESOURCE_REPLICA,
)


@dataclass(frozen=True)
class ExecutionStorageGarbageRecord:
    """
    Immutable record of a storage resource marked for, and optionally
    already reclaimed by, garbage collection.

    The record is a value object only. It performs no scanning,
    marking, or collection of its own; identifying unused resources
    and reclaiming them is the responsibility of an execution storage
    garbage collection service, which produces a new record for every
    mark and a replacement for every collection rather than mutating
    an existing one. A record can never be built already deleted
    before it was marked, enforcing mark-before-deletion structurally.

    Attributes:
        record_id: The record's unique identifier
        resource_id: The identifier of the resource marked for
            collection
        resource_type: The kind of resource marked, one of
            RESOURCE_TYPES
        reason: Why the resource was marked
        marked_at: When the resource was marked
        deleted_at: When the resource was actually collected, or None
            if it has not been collected yet
    """

    record_id: str

    resource_id: str

    resource_type: str

    reason: str

    marked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    deleted_at: datetime = None

    def __post_init__(self):
        self._require_text(self.record_id, "record ID")
        self._require_text(self.resource_id, "resource ID")
        self._require_text(self.reason, "reason")

        if self.resource_type not in RESOURCE_TYPES:
            raise ExecutionStorageGarbageRecordError(
                f"Cannot build an execution storage garbage record with an unknown "
                f"resource_type: {self.resource_type!r}."
            )

        if self.marked_at is None or not isinstance(self.marked_at, datetime):
            raise ExecutionStorageGarbageRecordError(
                "Cannot build an execution storage garbage record with a non-datetime marked_at."
            )

        if self.deleted_at is not None:
            if not isinstance(self.deleted_at, datetime):
                raise ExecutionStorageGarbageRecordError(
                    "Cannot build an execution storage garbage record with a non-datetime "
                    "deleted_at."
                )

            if self.deleted_at < self.marked_at:
                raise ExecutionStorageGarbageRecordError(
                    "Cannot build an execution storage garbage record deleted before it was "
                    "marked."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageGarbageRecordError(
                f"Cannot build an execution storage garbage record with an empty or blank "
                f"{field_name}."
            )
