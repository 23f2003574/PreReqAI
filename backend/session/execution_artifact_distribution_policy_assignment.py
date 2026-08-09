from dataclasses import (
    dataclass,
)

from .execution_artifact_distribution_policy_error import (
    ExecutionArtifactDistributionPolicyError,
)


@dataclass(frozen=True)
class ExecutionArtifactDistributionPolicyAssignment:
    """
    Immutable record binding a distribution policy to a channel as
    that channel's single active policy.

    The assignment is a value object only. It performs no validation
    of its own; assigning, removing, and looking up a channel's
    active policy is the responsibility of an execution artifact
    distribution policy service.

    Attributes:
        policy_id: The identifier of the policy assigned
        channel_id: The identifier of the channel it is assigned to
    """

    policy_id: str

    channel_id: str

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.channel_id, "channel ID")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionPolicyError(
                f"Cannot build a distribution policy assignment with an empty or blank {field_name}."
            )
