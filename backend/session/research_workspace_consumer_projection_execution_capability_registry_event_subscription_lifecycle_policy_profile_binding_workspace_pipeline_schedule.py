from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_scheduler_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedule:
    """
    Immutable request to run a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution pipeline no earlier than a given
    time, optionally once other schedules have themselves run.

    The schedule is a value object only. It performs no waiting, no
    dependency checking, and no dispatch. Waiting, dependency
    checking, and dispatch are the responsibility of a pipeline
    scheduler service.

    Attributes:
        schedule_id: The schedule's unique identifier
        pipeline_id: The identifier of the pipeline to run
        start_at: The earliest time the pipeline may run
        execution_window: How many seconds after start_at the
            schedule remains eligible to run; must be greater than
            zero
        depends_on: The identifiers of other schedules that must have
            already been dispatched before this one becomes eligible,
            empty if none apply
    """

    schedule_id: str

    pipeline_id: str

    start_at: datetime

    execution_window: float

    depends_on: tuple = field(default_factory=tuple)

    def __post_init__(self):
        if self.schedule_id is None or not self.schedule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                "Cannot build a pipeline schedule with an empty or blank schedule ID."
            )

        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                "Cannot build a pipeline schedule with an empty or blank pipeline ID."
            )

        if self.start_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                "Cannot build a pipeline schedule with a None start_at."
            )

        if (
            self.execution_window is None
            or isinstance(self.execution_window, bool)
            or not isinstance(self.execution_window, (int, float))
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                "Cannot build a pipeline schedule with a non-numeric execution_window."
            )

        if self.execution_window <= 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                f"Cannot build a pipeline schedule with execution_window {self.execution_window!r}; "
                "execution_window must be greater than zero."
            )

        if self.depends_on is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                "Cannot build a pipeline schedule with None depends_on."
            )

        for dependency_id in self.depends_on:
            if dependency_id is None or not str(dependency_id).strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                    "Cannot build a pipeline schedule with a blank dependency schedule ID."
                )
