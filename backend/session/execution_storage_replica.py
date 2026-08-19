from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_storage_replica_error import (
    ExecutionStorageReplicaError,
)

STATUS_SYNCED = "SYNCED"

STATUS_FAILED = "FAILED"

STATUSES = (
    STATUS_SYNCED,
    STATUS_FAILED,
)


@dataclass(frozen=True)
class ExecutionStorageReplica:
    """
    Immutable snapshot of a volume's replication onto a storage
    target, for durability and failover.

    The replica is a value object only. It performs no replication
    accounting of its own; replicating, syncing, and verifying
    replicas is the responsibility of an execution storage
    replication service, which produces a new snapshot for every
    transition rather than mutating an existing one.

    Attributes:
        replica_id: The replica's unique identifier
        volume_id: The identifier of the volume this replica was
            replicated from
        target: The identifier of the storage target this replica is
            held on
        status: The replica's current status, one of STATUSES
        checksum: A checksum computed at the replica's last
            successful sync, used to verify its integrity
        replicated_at: When the replica last completed a successful
            sync
    """

    replica_id: str

    volume_id: str

    target: str

    status: str

    checksum: str

    replicated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.replica_id, "replica ID")
        self._require_text(self.volume_id, "volume ID")
        self._require_text(self.target, "target")
        self._require_text(self.checksum, "checksum")

        if self.status not in STATUSES:
            raise ExecutionStorageReplicaError(
                f"Cannot build an execution storage replica with an unknown status: {self.status!r}."
            )

        if self.replicated_at is None or not isinstance(self.replicated_at, datetime):
            raise ExecutionStorageReplicaError(
                "Cannot build an execution storage replica with a non-datetime replicated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageReplicaError(
                f"Cannot build an execution storage replica with an empty or blank {field_name}."
            )
