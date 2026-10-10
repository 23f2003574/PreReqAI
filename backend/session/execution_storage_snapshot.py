from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from numbers import (
    Real,
)

from .execution_storage_snapshot_error import (
    ExecutionStorageSnapshotError,
)


@dataclass(frozen=True)
class ExecutionStorageSnapshot:
    """
    Immutable point-in-time capture of an execution volume, taken for
    recovery and rollback.

    The snapshot is a value object only, and frozen: once captured,
    none of its fields ever change. Capturing and restoring snapshots
    is the responsibility of an execution storage snapshot service,
    which produces a new record for every capture rather than
    mutating an existing one.

    Attributes:
        snapshot_id: The snapshot's unique identifier
        volume_id: The identifier of the volume this snapshot was
            captured from
        size: The size of the volume at the moment of capture; must
            be a positive number
        checksum: A checksum computed over the snapshot's identity
            and content, used to verify its integrity
        created_at: When the snapshot was captured
    """

    snapshot_id: str

    volume_id: str

    size: float

    checksum: str

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.snapshot_id, "snapshot ID")
        self._require_text(self.volume_id, "volume ID")
        self._require_text(self.checksum, "checksum")

        if self.size is None or isinstance(self.size, bool) or not isinstance(self.size, Real) or self.size <= 0:
            raise ExecutionStorageSnapshotError(
                f"Cannot build an execution storage snapshot with a non-positive size: {self.size!r}."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ExecutionStorageSnapshotError(
                "Cannot build an execution storage snapshot with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageSnapshotError(
                f"Cannot build an execution storage snapshot with an empty or blank {field_name}."
            )
