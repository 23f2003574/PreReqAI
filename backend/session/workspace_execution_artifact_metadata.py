from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Any

from .workspace_execution_artifact_metadata_error import (
    WorkspaceExecutionArtifactMetadataError,
)


@dataclass(frozen=True)
class WorkspaceExecutionArtifactMetadata:
    """
    Immutable record of a single searchable key/value entry attached
    to a workspace execution artifact.

    The metadata entry is a value object only. It performs no
    persistence of its own; setting, retrieving, removing, and
    searching metadata entries is the responsibility of a workspace
    execution artifact metadata service, which produces a new record
    for every transition rather than mutating an existing one.

    Attributes:
        artifact_id: The identifier of the workspace execution
            artifact this entry is attached to
        key: The metadata field name, unique among the entries of its
            artifact
        value: The metadata field's current value
        updated_at: When this entry was last set
    """

    artifact_id: str

    key: str

    value: Any

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.key, "key")

        if self.updated_at is None or not isinstance(self.updated_at, datetime):
            raise WorkspaceExecutionArtifactMetadataError(
                "Cannot build workspace execution artifact metadata with a non-datetime updated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactMetadataError(
                f"Cannot build workspace execution artifact metadata with an empty or blank {field_name}."
            )
