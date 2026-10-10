from dataclasses import (
    dataclass,
)

from .execution_artifact_access_error import (
    ExecutionArtifactAccessError,
)


@dataclass(frozen=True)
class ArtifactAccessResult:
    """
    Immutable outcome of an authorization check against an execution
    artifact.

    Attributes:
        allowed: Whether the checked principal may perform the
            checked operation
        reason: A human-readable explanation of the outcome
    """

    allowed: bool

    reason: str

    def __post_init__(self):
        if not isinstance(self.allowed, bool):
            raise ExecutionArtifactAccessError(
                "Cannot build an artifact access result with a non-boolean allowed."
            )

        if self.reason is None or not self.reason.strip():
            raise ExecutionArtifactAccessError(
                "Cannot build an artifact access result with an empty or blank reason."
            )
