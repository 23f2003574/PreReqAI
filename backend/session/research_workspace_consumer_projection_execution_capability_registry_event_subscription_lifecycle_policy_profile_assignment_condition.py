from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_condition_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentCondition:
    """
    Immutable representation of a condition governing profile assignments.

    Attributes:
        condition_id: The unique identifier of the condition.
        target_id: The identifier of the target the condition is applied to.
        profile_id: The identifier of the profile to assign if matched.
        expression: A string expression evaluated against runtime context (e.g. "env == 'production'").
        priority: The evaluation priority (higher values evaluated first).
    """

    condition_id: str

    target_id: str

    profile_id: str

    expression: str

    priority: int

    def __post_init__(self):
        if self.condition_id is None or not self.condition_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                "Cannot build a condition with an empty or blank condition ID."
            )

        if self.target_id is None or not self.target_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                "Cannot build a condition with an empty or blank target ID."
            )

        if self.profile_id is None or not self.profile_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                "Cannot build a condition with an empty or blank profile ID."
            )

        if self.expression is None or not self.expression.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                "Cannot build a condition with an empty or blank expression."
            )

        try:
            compile(self.expression, "<string>", "eval")
        except SyntaxError as e:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionError(
                f"Invalid expression syntax: {e}"
            )
