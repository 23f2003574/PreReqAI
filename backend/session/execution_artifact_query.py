from dataclasses import (
    dataclass,
    field,
)

from typing import Any

from .execution_artifact_discovery_error import (
    ExecutionArtifactDiscoveryError,
)


@dataclass(frozen=True)
class ExecutionArtifactQuery:
    """
    Immutable description of the criteria an execution artifact must
    exactly match to be returned by an execution artifact discovery
    service.

    The query is a value object only. It performs no searching of
    its own; evaluating it against known artifacts is the
    responsibility of an execution artifact discovery service.

    Attributes:
        session_id: If given, only artifacts registered under this
            exact session ID match
        type: If given, only artifacts of this exact type match
        tag: If given, only artifacts currently tagged with this
            exact tag match
        metadata: If given, only artifacts carrying every one of
            these key/value pairs as metadata match
    """

    session_id: str | None = None

    type: str | None = None

    tag: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self):
        if self.session_id is not None:
            self._require_text(self.session_id, "session ID")

        if self.type is not None:
            self._require_text(self.type, "type")

        if self.tag is not None:
            self._require_text(self.tag, "tag")

        if not isinstance(self.metadata, dict):
            raise ExecutionArtifactDiscoveryError(
                "Cannot build an execution artifact query with a non-dict metadata."
            )

        for key in self.metadata:
            self._require_text(key, "metadata key")

        if (
            self.session_id is None
            and self.type is None
            and self.tag is None
            and not self.metadata
        ):
            raise ExecutionArtifactDiscoveryError(
                "Cannot build an execution artifact query with no criteria: at least one of session_id, "
                "type, tag, or metadata must be given."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactDiscoveryError(
                f"Cannot build an execution artifact query with an empty or blank {field_name}."
            )
