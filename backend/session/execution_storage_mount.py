from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_storage_mount_error import (
    ExecutionStorageMountError,
)

MODE_READ_ONLY = "READ_ONLY"

MODE_READ_WRITE = "READ_WRITE"

MODES = (
    MODE_READ_ONLY,
    MODE_READ_WRITE,
)


@dataclass(frozen=True)
class ExecutionStorageMount:
    """
    Immutable record of a runtime's controlled mount of a persistent
    execution volume.

    The mount is a value object only. It performs no mount lifecycle
    accounting of its own; mounting and unmounting volumes is the
    responsibility of an execution storage mount service, which
    produces a new record for every mount rather than mutating an
    existing one.

    Attributes:
        mount_id: The mount's unique identifier
        volume_id: The identifier of the volume this mount exposes
        runtime_id: The identifier of the runtime this mount was made
            for
        path: The path within the runtime this volume is mounted at
        mode: The mount's access mode, one of MODES
        mounted_at: When the mount was created
    """

    mount_id: str

    volume_id: str

    runtime_id: str

    path: str

    mode: str

    mounted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.mount_id, "mount ID")
        self._require_text(self.volume_id, "volume ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.path, "path")

        if self.mode not in MODES:
            raise ExecutionStorageMountError(
                f"Cannot build an execution storage mount with an unknown mode: {self.mode!r}."
            )

        if self.mounted_at is None or not isinstance(self.mounted_at, datetime):
            raise ExecutionStorageMountError(
                "Cannot build an execution storage mount with a non-datetime mounted_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageMountError(
                f"Cannot build an execution storage mount with an empty or blank {field_name}."
            )
