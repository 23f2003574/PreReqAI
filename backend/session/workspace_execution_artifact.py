from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .workspace_execution_artifact_error import (
    WorkspaceExecutionArtifactError,
)

ARTIFACT_TYPE_FILE = "FILE"

ARTIFACT_TYPE_DIRECTORY = "DIRECTORY"

ARTIFACT_TYPE_MODEL = "MODEL"

ARTIFACT_TYPE_DATASET = "DATASET"

ARTIFACT_TYPES = (
    ARTIFACT_TYPE_FILE,
    ARTIFACT_TYPE_DIRECTORY,
    ARTIFACT_TYPE_MODEL,
    ARTIFACT_TYPE_DATASET,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_REMOVED = "REMOVED"

STATUSES = (
    STATUS_ACTIVE,
    STATUS_REMOVED,
)


@dataclass(frozen=True)
class WorkspaceExecutionArtifact:
    """
    Immutable snapshot of an addressable output artifact produced by
    an execution runtime.

    The artifact is a value object only. It performs no registry
    accounting of its own; registering, retrieving, listing, and
    removing artifacts is the responsibility of an execution artifact
    registry service, which produces a new snapshot for every
    transition rather than mutating an existing one.

    Attributes:
        artifact_id: The artifact's unique identifier
        runtime_id: The identifier of the execution runtime that
            produced this artifact
        name: A human-readable name for the artifact, unique among the
            active artifacts of its runtime
        artifact_type: The kind of artifact this is, one of
            ARTIFACT_TYPES
        location: Where the artifact's contents can be found, e.g. a
            file path or URL
        status: The artifact's current status, one of STATUSES
        created_at: When this artifact was registered
    """

    artifact_id: str

    runtime_id: str

    name: str

    artifact_type: str

    location: str

    status: str = STATUS_ACTIVE

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.name, "name")
        self._require_text(self.location, "location")

        if self.artifact_type not in ARTIFACT_TYPES:
            raise WorkspaceExecutionArtifactError(
                f"Cannot build a workspace execution artifact with an unknown artifact type: "
                f"{self.artifact_type!r}."
            )

        if self.status not in STATUSES:
            raise WorkspaceExecutionArtifactError(
                f"Cannot build a workspace execution artifact with an unknown status: {self.status!r}."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise WorkspaceExecutionArtifactError(
                "Cannot build a workspace execution artifact with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactError(
                f"Cannot build a workspace execution artifact with an empty or blank {field_name}."
            )
