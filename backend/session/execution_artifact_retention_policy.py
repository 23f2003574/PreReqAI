from dataclasses import (
    dataclass,
)

from typing import Optional

from .execution_artifact_retention_error import (
    ExecutionArtifactRetentionError,
)


@dataclass(frozen=True)
class ExecutionArtifactRetentionPolicy:
    """
    Immutable rule set describing how many versions, and for how
    long, an execution artifact's version history should be kept.

    The policy is a value object only. It performs no expiration of
    its own; evaluating and applying a policy against an artifact's
    version history is the responsibility of an execution artifact
    retention service.

    Attributes:
        policy_id: The policy's unique identifier
        max_versions: The greatest number of versions to keep,
            newest first, or None to not limit by count
        max_age_seconds: The greatest age, in seconds, a version may
            reach before it is eligible for removal, or None to not
            limit by age
    """

    policy_id: str

    max_versions: Optional[int] = None

    max_age_seconds: Optional[float] = None

    def __post_init__(self):
        if self.policy_id is None or not self.policy_id.strip():
            raise ExecutionArtifactRetentionError(
                "Cannot build a retention policy with an empty or blank policy ID."
            )

        if self.max_versions is None and self.max_age_seconds is None:
            raise ExecutionArtifactRetentionError(
                "Cannot build a retention policy with neither max_versions nor max_age_seconds set."
            )

        if self.max_versions is not None:
            if not isinstance(self.max_versions, int) or isinstance(self.max_versions, bool):
                raise ExecutionArtifactRetentionError(
                    "Cannot build a retention policy with a non-integer max_versions."
                )

            if self.max_versions < 1:
                raise ExecutionArtifactRetentionError(
                    "Cannot build a retention policy with a max_versions below 1."
                )

        if self.max_age_seconds is not None:
            if not isinstance(self.max_age_seconds, (int, float)) or isinstance(self.max_age_seconds, bool):
                raise ExecutionArtifactRetentionError(
                    "Cannot build a retention policy with a non-numeric max_age_seconds."
                )

            if self.max_age_seconds <= 0:
                raise ExecutionArtifactRetentionError(
                    "Cannot build a retention policy with a non-positive max_age_seconds."
                )
