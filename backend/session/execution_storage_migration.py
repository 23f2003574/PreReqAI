from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_storage_migration_error import (
    ExecutionStorageMigrationError,
)

STATUS_IN_PROGRESS = "IN_PROGRESS"

STATUS_VERIFIED = "VERIFIED"

STATUS_FAILED = "FAILED"

STATUS_COMPLETED = "COMPLETED"

STATUS_ROLLED_BACK = "ROLLED_BACK"

STATUSES = (
    STATUS_IN_PROGRESS,
    STATUS_VERIFIED,
    STATUS_FAILED,
    STATUS_COMPLETED,
    STATUS_ROLLED_BACK,
)


@dataclass(frozen=True)
class ExecutionStorageMigration:
    """
    Immutable snapshot of a volume's move from a source storage
    target to a destination target.

    The migration is a value object only. It performs no copying,
    verification, or cutover of its own; starting, verifying,
    completing, and rolling back migrations is the responsibility of
    an execution storage migration service, which produces a new
    snapshot for every transition rather than mutating an existing
    one.

    Attributes:
        migration_id: The migration's unique identifier
        volume_id: The identifier of the volume being migrated
        source_target: The target the volume is being migrated away
            from; preserved untouched unless and until the migration
            completes
        destination_target: The target the volume is being migrated
            onto
        status: The migration's current status, one of STATUSES
        checksum: The checksum captured for the destination at the
            start of the migration, checked again at verification
        started_at: When the migration was started
        completed_at: When the migration completed, or None if it has
            not (yet) completed
    """

    migration_id: str

    volume_id: str

    source_target: str

    destination_target: str

    status: str

    checksum: str

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    completed_at: datetime = None

    def __post_init__(self):
        self._require_text(self.migration_id, "migration ID")
        self._require_text(self.volume_id, "volume ID")
        self._require_text(self.source_target, "source target")
        self._require_text(self.destination_target, "destination target")
        self._require_text(self.checksum, "checksum")

        if self.source_target == self.destination_target:
            raise ExecutionStorageMigrationError(
                "Cannot build an execution storage migration with the same source and "
                "destination target."
            )

        if self.status not in STATUSES:
            raise ExecutionStorageMigrationError(
                f"Cannot build an execution storage migration with an unknown status: "
                f"{self.status!r}."
            )

        if self.started_at is None or not isinstance(self.started_at, datetime):
            raise ExecutionStorageMigrationError(
                "Cannot build an execution storage migration with a non-datetime started_at."
            )

        if self.status == STATUS_COMPLETED:
            if self.completed_at is None or not isinstance(self.completed_at, datetime):
                raise ExecutionStorageMigrationError(
                    "Cannot build a COMPLETED execution storage migration without a datetime "
                    "completed_at."
                )

            if self.completed_at < self.started_at:
                raise ExecutionStorageMigrationError(
                    "Cannot build an execution storage migration completed before it was started."
                )
        elif self.completed_at is not None:
            raise ExecutionStorageMigrationError(
                f"Cannot build a {self.status!r} execution storage migration with a "
                f"completed_at set."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageMigrationError(
                f"Cannot build an execution storage migration with an empty or blank {field_name}."
            )
