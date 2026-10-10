from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_event_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventResult:
    """
    Immutable outcome produced after publishing or dispatching a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace pipeline
    event.

    The result is a value object only. It performs no publication and
    no dispatch. Publication and dispatch are the responsibility of a
    pipeline event bus.

    Attributes:
        published: Whether the event was newly queued (publish()) or
            newly dispatched (dispatch_pending()); False when the
            event's ID had already been delivered or was already
            queued, so it was not queued or dispatched again
        subscribers_notified: How many subscribed handlers ran to
            completion without raising; always 0 for a publish()
            result, since dispatch happens separately
    """

    published: bool

    subscribers_notified: int

    def __post_init__(self):
        if not isinstance(self.published, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot build a pipeline event result with a non-boolean published flag."
            )

        if not isinstance(self.subscribers_notified, int) or isinstance(self.subscribers_notified, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot build a pipeline event result with a non-integer subscribers_notified."
            )

        if self.subscribers_notified < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot build a pipeline event result with a negative subscribers_notified."
            )
