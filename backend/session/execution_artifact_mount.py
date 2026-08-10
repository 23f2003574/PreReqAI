from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
)

from uuid import uuid4

from .execution_artifact_mount_error import (
    ExecutionArtifactMountError,
)


@dataclass(frozen=True)
class ExecutionArtifactMount:
    """
    Immutable record of a temporary consumer mount exposing a
    retrieved execution artifact at a filesystem-like path until it
    expires.

    The mount is a value object only. It performs no retrieval,
    expiry, or cleanup of its own; creating, releasing, and cleaning
    up mounts is the responsibility of an execution artifact mount
    service.

    Attributes:
        mount_id: The mount's unique identifier
        artifact_id: The identifier of the mounted artifact
        consumer: Who the mount was created for
        path: Where the artifact is exposed while the mount is active
        expires_at: When this mount stops being active
    """

    artifact_id: str

    consumer: str

    path: str

    expires_at: datetime

    mount_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.mount_id, "mount ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.consumer, "consumer")
        self._require_text(self.path, "path")

        if not isinstance(self.expires_at, datetime):
            raise ExecutionArtifactMountError(
                "Cannot build an execution artifact mount with a non-datetime expires_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactMountError(
                f"Cannot build an execution artifact mount with an empty or blank {field_name}."
            )
