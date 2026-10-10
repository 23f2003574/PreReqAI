from dataclasses import (
    dataclass,
)

from .execution_artifact_retrieval_error import (
    ExecutionArtifactRetrievalError,
)


@dataclass(frozen=True)
class ExecutionArtifactRetrievalRequest:
    """
    Immutable description of a consumer's request to retrieve an
    execution artifact.

    The request is a value object only. It performs no retrieval or
    authorization of its own; resolving and validating it against
    known artifacts, versions, and access grants is the
    responsibility of an execution artifact retrieval service.

    Attributes:
        artifact_id: The identifier of the artifact being requested
        consumer: Who is requesting the artifact, checked against
            existing access grants
        version: The exact version number requested. If omitted, the
            artifact's latest version is used
    """

    artifact_id: str

    consumer: str

    version: int | None = None

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.consumer, "consumer")

        if self.version is not None and (
            isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1
        ):
            raise ExecutionArtifactRetrievalError(
                "Cannot build an execution artifact retrieval request with a version below 1."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactRetrievalError(
                f"Cannot build an execution artifact retrieval request with an empty or blank {field_name}."
            )
