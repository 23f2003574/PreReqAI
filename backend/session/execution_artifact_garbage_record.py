from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Optional

from uuid import uuid4

from .execution_artifact_garbage_collection_error import (
    ExecutionArtifactGarbageCollectionError,
)

REASON_RETENTION_EXPIRED = "RETENTION_EXPIRED"


@dataclass(frozen=True)
class ExecutionArtifactGarbageRecord:
    """
    Immutable record of an artifact version marked, and eventually
    collected, because it has passed retention and is no longer
    protected.

    The record is a value object only. It performs no retention or
    protection evaluation of its own; scanning, marking, and
    collecting versions is the responsibility of an execution
    artifact garbage collection service, which produces a new
    snapshot for every transition rather than mutating an existing
    one.

    Attributes:
        artifact_id: The identifier of the artifact this version
            belongs to
        version_id: The identifier of the version this record
            describes
        reason: Why this version was marked for collection
        record_id: The record's unique identifier
        marked_at: When this version was marked for collection
        deleted_at: When this version was actually collected, or None
            if it has been marked but not yet collected
    """

    artifact_id: str

    version_id: str

    reason: str

    record_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    marked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    deleted_at: Optional[datetime] = None

    def __post_init__(self):
        self._require_text(self.record_id, "record ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.version_id, "version ID")
        self._require_text(self.reason, "reason")

        if not isinstance(self.marked_at, datetime):
            raise ExecutionArtifactGarbageCollectionError(
                "Cannot build an execution artifact garbage record with a non-datetime marked_at."
            )

        if self.deleted_at is not None and not isinstance(self.deleted_at, datetime):
            raise ExecutionArtifactGarbageCollectionError(
                "Cannot build an execution artifact garbage record with a non-datetime deleted_at."
            )

        if self.deleted_at is not None and self.deleted_at < self.marked_at:
            raise ExecutionArtifactGarbageCollectionError(
                "Cannot build an execution artifact garbage record with a deleted_at before its "
                "marked_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactGarbageCollectionError(
                f"Cannot build an execution artifact garbage record with an empty or blank "
                f"{field_name}."
            )
