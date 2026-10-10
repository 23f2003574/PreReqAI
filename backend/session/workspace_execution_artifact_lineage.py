from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Optional

from uuid import uuid4

from .workspace_execution_artifact_lineage_error import (
    WorkspaceExecutionArtifactLineageError,
)


@dataclass(frozen=True)
class WorkspaceExecutionArtifactLineage:
    """
    Immutable record of which runtime, artifact, and parent artifact
    version produced a single artifact version.

    The lineage record is a value object only. It performs no
    validation of whether the referenced runtime, artifact, or parent
    version genuinely exist; recording and tracing lineage is the
    responsibility of an execution artifact lineage service.

    Attributes:
        artifact_id: The identifier of the artifact whose version this
            record describes the origin of
        version_id: The identifier of the version this record
            describes the origin of
        runtime_id: The identifier of the execution runtime that
            produced version_id
        parent_artifact_id: The identifier of the artifact whose
            version was consumed to produce version_id, or None if
            version_id has no parent
        parent_version_id: The identifier of the version that was
            consumed to produce version_id, or None if version_id has
            no parent
        lineage_id: The record's unique identifier
        created_at: When this lineage record was created
    """

    artifact_id: str

    version_id: str

    runtime_id: str

    parent_artifact_id: Optional[str] = None

    parent_version_id: Optional[str] = None

    lineage_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.lineage_id, "lineage ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.version_id, "version ID")
        self._require_text(self.runtime_id, "runtime ID")

        if (self.parent_artifact_id is None) != (self.parent_version_id is None):
            raise WorkspaceExecutionArtifactLineageError(
                "Cannot build a workspace execution artifact lineage record with only one of "
                "parent_artifact_id and parent_version_id set."
            )

        if self.parent_artifact_id is not None:
            self._require_text(self.parent_artifact_id, "parent artifact ID")
            self._require_text(self.parent_version_id, "parent version ID")

            if self.parent_version_id == self.version_id:
                raise WorkspaceExecutionArtifactLineageError(
                    f"Version ID {self.version_id!r} cannot be listed as its own parent."
                )

        if not isinstance(self.created_at, datetime):
            raise WorkspaceExecutionArtifactLineageError(
                "Cannot build a workspace execution artifact lineage record with a non-datetime "
                "created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactLineageError(
                f"Cannot build a workspace execution artifact lineage record with an empty or "
                f"blank {field_name}."
            )
