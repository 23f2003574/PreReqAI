from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_timeout_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCancellationResult:
    """
    Immutable outcome produced after cancelling a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace pipeline stage.

    The result is a value object only. It performs no cancellation.
    Cancellation is the responsibility of a pipeline timeout service.

    Attributes:
        stage_id: The identifier of the stage that was cancelled
        cancelled: Whether the stage was successfully cancelled
        reason: Why the stage was cancelled
    """

    stage_id: str

    cancelled: bool

    reason: str

    def __post_init__(self):
        if self.stage_id is None or not self.stage_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                "Cannot build a pipeline cancellation result with an empty or blank stage ID."
            )

        if not isinstance(self.cancelled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                "Cannot build a pipeline cancellation result with a non-boolean cancelled flag."
            )

        if self.reason is None or not self.reason.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                "Cannot build a pipeline cancellation result with an empty or blank reason."
            )
