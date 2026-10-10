from dataclasses import (
    dataclass,
)

from .execution_artifact_retrieval_error import (
    ExecutionArtifactRetrievalError,
)


@dataclass(frozen=True)
class ExecutionArtifactRetrievalResult:
    """
    Immutable outcome of a successful execution artifact retrieval,
    identifying exactly which version was resolved and where its
    contents can be found.

    Attributes:
        artifact_id: The identifier of the retrieved artifact
        version: The version number that was resolved
        location: Where that version's contents can be found, e.g. a
            file path or URL
    """

    artifact_id: str

    version: int

    location: str

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.location, "location")

        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ExecutionArtifactRetrievalError(
                "Cannot build an execution artifact retrieval result with a version below 1."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactRetrievalError(
                f"Cannot build an execution artifact retrieval result with an empty or blank {field_name}."
            )
