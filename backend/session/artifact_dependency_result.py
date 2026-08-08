from dataclasses import (
    dataclass,
)

from .execution_artifact_dependency_error import (
    ExecutionArtifactDependencyError,
)


@dataclass(frozen=True)
class ArtifactDependencyResult:
    """
    Immutable outcome of validating whether an artifact's declared
    dependencies are currently satisfied.

    Attributes:
        satisfied: Whether every declared dependency is currently met
        reason: A human-readable explanation of the outcome
    """

    satisfied: bool

    reason: str

    def __post_init__(self):
        if not isinstance(self.satisfied, bool):
            raise ExecutionArtifactDependencyError(
                "Cannot build an artifact dependency result with a non-boolean satisfied."
            )

        if self.reason is None or not self.reason.strip():
            raise ExecutionArtifactDependencyError(
                "Cannot build an artifact dependency result with an empty or blank reason."
            )
