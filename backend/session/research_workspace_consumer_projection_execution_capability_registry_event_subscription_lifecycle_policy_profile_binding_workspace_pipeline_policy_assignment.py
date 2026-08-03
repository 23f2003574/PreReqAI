from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_execution_policy_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePolicyAssignment:
    """
    Immutable link between a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution pipeline and the execution policy currently
    applied to it.

    The assignment is a value object only. It performs no assignment
    logic. Assignment is the responsibility of a pipeline execution
    policy service.

    Attributes:
        pipeline_id: The identifier of the assigned pipeline
        policy_id: The identifier of the policy it is assigned to
    """

    pipeline_id: str

    policy_id: str

    def __post_init__(self):
        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                "Cannot build a pipeline policy assignment with an empty or blank pipeline ID."
            )

        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                "Cannot build a pipeline policy assignment with an empty or blank policy ID."
            )
