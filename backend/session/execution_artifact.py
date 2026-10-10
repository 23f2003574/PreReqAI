from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Any

from .execution_artifact_error import (
    ExecutionArtifactError,
)


@dataclass(frozen=True)
class ExecutionArtifact:
    """
    Immutable record of an artifact produced during an execution
    session, such as a generated file, report, or log.

    The artifact is a value object only. It performs no persistence
    of its own; registering, retrieving, listing, and removing
    artifacts is the responsibility of an execution artifact service.

    Attributes:
        artifact_id: The artifact's unique identifier
        session_id: The identifier of the execution session that
            produced this artifact
        name: A human-readable name for the artifact
        type: The kind of artifact this is, e.g. "log" or "report"
        location: Where the artifact's contents can be found, e.g. a
            file path or URL
        created_at: When this artifact was produced
        metadata: Arbitrary additional details about the artifact
    """

    artifact_id: str

    session_id: str

    name: str

    type: str

    location: str

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.name, "name")
        self._require_text(self.type, "type")
        self._require_text(self.location, "location")

        if not isinstance(self.created_at, datetime):
            raise ExecutionArtifactError(
                "Cannot build an execution artifact with a non-datetime created_at."
            )

        if not isinstance(self.metadata, dict):
            raise ExecutionArtifactError(
                "Cannot build an execution artifact with a non-dict metadata."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactError(
                f"Cannot build an execution artifact with an empty or blank {field_name}."
            )
