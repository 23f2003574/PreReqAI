from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_timeout_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy:
    """
    Immutable timeout configuration for a single consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace pipeline stage.

    The policy is a value object only. It performs no timing and no
    cancellation. Timing and cancellation are the responsibility of a
    pipeline timeout service.

    Attributes:
        timeout_seconds: How long the stage may run before it is
            considered timed out; must be greater than zero
        cancel_on_timeout: Whether a timed-out stage should be
            cancelled automatically
        notify_on_timeout: Whether a timed-out stage should be
            reported to whoever is watching the pipeline
    """

    timeout_seconds: float

    cancel_on_timeout: bool

    notify_on_timeout: bool

    def __post_init__(self):
        if self.timeout_seconds is None or isinstance(self.timeout_seconds, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                "Cannot build a pipeline timeout policy with a non-numeric timeout."
            )

        if not isinstance(self.timeout_seconds, (int, float)):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                "Cannot build a pipeline timeout policy with a non-numeric timeout."
            )

        if self.timeout_seconds <= 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                f"Cannot build a pipeline timeout policy with a timeout of {self.timeout_seconds!r}; "
                "timeout_seconds must be greater than zero."
            )

        if not isinstance(self.cancel_on_timeout, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                "Cannot build a pipeline timeout policy with a non-boolean cancel_on_timeout."
            )

        if not isinstance(self.notify_on_timeout, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                "Cannot build a pipeline timeout policy with a non-boolean notify_on_timeout."
            )
