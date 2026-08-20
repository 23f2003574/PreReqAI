from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .workspace_execution_artifact_version_error import (
    WorkspaceExecutionArtifactVersionError,
)


@dataclass(frozen=True)
class WorkspaceExecutionArtifactVersion:
    """
    Immutable snapshot of a workspace execution artifact's contents
    at a single point in time. Creating a new version never
    overwrites or mutates a prior one.

    The version is a value object only. It performs no persistence
    of its own; creating and looking up versions is the
    responsibility of a workspace execution artifact version service.

    Attributes:
        artifact_id: The identifier of the workspace execution
            artifact this version belongs to
        version: The version number, starting at 1 for an artifact's
            first version and increasing by 1 for each version after
        location: Where this version's contents can be found, e.g. a
            file path or URL
        checksum: A content checksum for this version, e.g. a hash of
            its contents
        version_id: The version's unique identifier
        created_at: When this version was created
    """

    artifact_id: str

    version: int

    location: str

    checksum: str

    version_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.version_id, "version ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.location, "location")
        self._require_text(self.checksum, "checksum")

        if not isinstance(self.version, int) or isinstance(self.version, bool):
            raise WorkspaceExecutionArtifactVersionError(
                "Cannot build a workspace execution artifact version with a non-integer version."
            )

        if self.version < 1:
            raise WorkspaceExecutionArtifactVersionError(
                "Cannot build a workspace execution artifact version with a version below 1."
            )

        if not isinstance(self.created_at, datetime):
            raise WorkspaceExecutionArtifactVersionError(
                "Cannot build a workspace execution artifact version with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactVersionError(
                f"Cannot build a workspace execution artifact version with an empty or blank {field_name}."
            )
