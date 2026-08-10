from dataclasses import (
    dataclass,
)

from .execution_artifact_discovery_error import (
    ExecutionArtifactDiscoveryError,
)


@dataclass(frozen=True)
class ExecutionArtifactSearchResult:
    """
    Immutable single hit produced by an execution artifact discovery
    service, identifying a matching artifact and how many of the
    query's criteria it satisfied.

    Attributes:
        artifact_id: The identifier of the matching artifact
        score: How many of the query's criteria this artifact
            satisfied
    """

    artifact_id: str

    score: float

    def __post_init__(self):
        if not isinstance(self.artifact_id, str) or not self.artifact_id.strip():
            raise ExecutionArtifactDiscoveryError(
                "Cannot build an execution artifact search result with an empty or blank artifact ID."
            )

        if isinstance(self.score, bool) or not isinstance(self.score, (int, float)):
            raise ExecutionArtifactDiscoveryError(
                "Cannot build an execution artifact search result with a non-numeric score."
            )

        if self.score < 0:
            raise ExecutionArtifactDiscoveryError(
                "Cannot build an execution artifact search result with a negative score."
            )
