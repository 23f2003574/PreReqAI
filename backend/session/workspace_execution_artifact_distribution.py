from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .workspace_execution_artifact_distribution_error import (
    WorkspaceExecutionArtifactDistributionError,
)

STATUS_PUBLISHED = "PUBLISHED"

STATUS_FAILED = "FAILED"

STATUS_REMOVED = "REMOVED"

STATUSES = (
    STATUS_PUBLISHED,
    STATUS_FAILED,
    STATUS_REMOVED,
)


@dataclass(frozen=True)
class WorkspaceExecutionArtifactDistribution:
    """
    Immutable record of a single attempt to make a verified artifact
    version available at a target execution environment, without
    modifying the version's contents.

    The distribution is a value object only. It performs no integrity
    verification of its own; publishing, verifying, and removing
    distributions is the responsibility of an execution artifact
    distribution service, which produces a new snapshot for every
    transition rather than mutating an existing one.

    Attributes:
        artifact_id: The identifier of the artifact whose version was
            distributed
        version_id: The identifier of the version that was
            distributed
        target: The execution environment this version was
            distributed to
        status: PUBLISHED if the checksum observed at target matched
            the version's recorded checksum after publishing, FAILED
            if it did not, or REMOVED once withdrawn; one of STATUSES
        checksum: The checksum observed at target at the moment of
            this attempt
        distribution_id: The distribution's unique identifier
        distributed_at: When this attempt was recorded
    """

    artifact_id: str

    version_id: str

    target: str

    status: str

    checksum: str

    distribution_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    distributed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.distribution_id, "distribution ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.version_id, "version ID")
        self._require_text(self.target, "target")
        self._require_text(self.checksum, "checksum")

        if self.status not in STATUSES:
            raise WorkspaceExecutionArtifactDistributionError(
                f"Cannot build a workspace execution artifact distribution with an unknown "
                f"status: {self.status!r}."
            )

        if not isinstance(self.distributed_at, datetime):
            raise WorkspaceExecutionArtifactDistributionError(
                "Cannot build a workspace execution artifact distribution with a non-datetime "
                "distributed_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactDistributionError(
                f"Cannot build a workspace execution artifact distribution with an empty or "
                f"blank {field_name}."
            )
