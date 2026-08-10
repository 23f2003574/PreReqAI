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

from .execution_artifact_consumption_snapshot_error import (
    ExecutionArtifactConsumptionSnapshotError,
)


@dataclass(frozen=True)
class ExecutionArtifactConsumptionSnapshot:
    """
    Immutable record of the exact artifact versions a consumption
    session held at a single point in time.

    The snapshot is a value object only. It performs no capturing or
    restoring of its own; creating, restoring, and looking up
    snapshots is the responsibility of an execution artifact
    consumption snapshot service.

    Attributes:
        snapshot_id: The snapshot's unique identifier
        consumption_id: The identifier of the consumption session
            this snapshot was captured from
        artifact_versions: The exact version number captured for
            each artifact the session was consuming, keyed by
            artifact ID
        created_at: When this snapshot was captured
    """

    consumption_id: str

    artifact_versions: dict

    snapshot_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.snapshot_id, "snapshot ID")
        self._require_text(self.consumption_id, "consumption ID")

        if not isinstance(self.created_at, datetime):
            raise ExecutionArtifactConsumptionSnapshotError(
                "Cannot build an execution artifact consumption snapshot with a non-datetime created_at."
            )

        if not isinstance(self.artifact_versions, dict):
            raise ExecutionArtifactConsumptionSnapshotError(
                "Cannot build an execution artifact consumption snapshot with a non-dict artifact_versions."
            )

        for artifact_id, version in self.artifact_versions.items():
            if not isinstance(artifact_id, str) or not artifact_id.strip():
                raise ExecutionArtifactConsumptionSnapshotError(
                    "Cannot build an execution artifact consumption snapshot with a blank or non-string "
                    "artifact ID."
                )

            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                raise ExecutionArtifactConsumptionSnapshotError(
                    f"Cannot build an execution artifact consumption snapshot with an invalid version for "
                    f"artifact ID {artifact_id!r}: version must be a positive integer."
                )

        object.__setattr__(self, "artifact_versions", MappingProxyType(dict(self.artifact_versions)))

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionSnapshotError(
                f"Cannot build an execution artifact consumption snapshot with an empty or blank {field_name}."
            )
