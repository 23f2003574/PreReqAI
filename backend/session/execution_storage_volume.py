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

from .execution_storage_volume_error import (
    ExecutionStorageVolumeError,
)

STATUS_AVAILABLE = "AVAILABLE"

STATUS_ATTACHED = "ATTACHED"

STATUSES = (
    STATUS_AVAILABLE,
    STATUS_ATTACHED,
)


@dataclass(frozen=True)
class ExecutionStorageVolume:
    """
    Immutable snapshot of a persistent storage volume that execution
    runtimes can attach and use.

    The volume is a value object only. It performs no attachment
    accounting of its own; creating, attaching, and detaching volumes
    is the responsibility of an execution storage volume service,
    which produces a new snapshot for every transition rather than
    mutating an existing one.

    Attributes:
        volume_id: The volume's unique identifier
        scope_id: The identifier of the scope this volume belongs to
        size: The volume's size; must be a positive number
        status: The volume's current status, one of STATUSES
        created_at: When the volume was created
    """

    volume_id: str

    scope_id: str

    size: float

    status: str = STATUS_AVAILABLE

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.volume_id, "volume ID")
        self._require_text(self.scope_id, "scope ID")

        if self.size is None or isinstance(self.size, bool) or not isinstance(self.size, Real) or self.size <= 0:
            raise ExecutionStorageVolumeError(
                f"Cannot build an execution storage volume with a non-positive size: {self.size!r}."
            )

        if self.status not in STATUSES:
            raise ExecutionStorageVolumeError(
                f"Cannot build an execution storage volume with an unknown status: {self.status!r}."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ExecutionStorageVolumeError(
                "Cannot build an execution storage volume with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageVolumeError(
                f"Cannot build an execution storage volume with an empty or blank {field_name}."
            )
