from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_scheduler_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineScheduleResult:
    """
    Immutable outcome produced after scheduling or rescheduling a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    pipeline.

    The result is a value object only. It performs no scheduling.
    Scheduling is the responsibility of a pipeline scheduler service.

    Attributes:
        scheduled: Whether the schedule was accepted
        next_execution: The earliest time the schedule is eligible to
            run
    """

    scheduled: bool

    next_execution: datetime

    def __post_init__(self):
        if not isinstance(self.scheduled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                "Cannot build a pipeline schedule result with a non-boolean scheduled flag."
            )

        if self.next_execution is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                "Cannot build a pipeline schedule result with a None next_execution."
            )
