from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_rollout_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError,
)

VALID_SESSION_POLICY_ROLLOUT_STRATEGIES = (
    "FULL",
    "PERCENTAGE",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRollout:
    """
    Immutable configuration describing how a specific published
    version of a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution session policy is gradually adopted by newly created
    sessions, instead of switching every session to it at once.

    The rollout is a value object only. It performs no adoption
    decision. Starting, stopping, and resolving sessions against a
    rollout are the responsibility of a session policy rollout
    service.

    Attributes:
        rollout_id: The rollout's unique identifier
        policy_id: The identifier of the policy this rollout concerns
        target_version: The version number newly created sessions are
            adopted onto, subject to strategy and percentage
        strategy: How target_version is adopted, one of "FULL" or
            "PERCENTAGE". Under "FULL", every newly created session
            adopts it. Under "PERCENTAGE", only a percentage of newly
            created sessions do
        percentage: What percentage of newly created sessions adopt
            target_version, from 0 to 100. Always 100 under "FULL"
    """

    rollout_id: str

    policy_id: str

    target_version: int

    strategy: str

    percentage: float

    def __post_init__(self):
        if self.rollout_id is None or not self.rollout_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                "Cannot build a session policy rollout with an empty or blank rollout ID."
            )

        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                "Cannot build a session policy rollout with an empty or blank policy ID."
            )

        if (
            self.target_version is None
            or isinstance(self.target_version, bool)
            or not isinstance(self.target_version, int)
            or self.target_version <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                f"Invalid session policy rollout target_version {self.target_version!r}; target_version must be "
                "a positive integer."
            )

        if self.strategy not in VALID_SESSION_POLICY_ROLLOUT_STRATEGIES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                f"Invalid session policy rollout strategy {self.strategy!r}. Must be one of "
                f"{VALID_SESSION_POLICY_ROLLOUT_STRATEGIES!r}."
            )

        if (
            self.percentage is None
            or isinstance(self.percentage, bool)
            or not isinstance(self.percentage, (int, float))
            or not (0 <= self.percentage <= 100)
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                f"Invalid session policy rollout percentage {self.percentage!r}; percentage must be a number "
                "from 0 to 100."
            )

        if self.strategy == "FULL" and self.percentage != 100:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                "Cannot build a session policy rollout with strategy 'FULL' and a percentage other than 100."
            )
