from dataclasses import (
    dataclass,
)

from datetime import datetime


from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_dashboard_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardEntry:
    """
    Immutable, point-in-time view of a single consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace execution pipeline, assembled
    for display rather than for driving execution.

    The entry is a value object only. It performs no querying.
    Querying is the responsibility of a pipeline dashboard service.

    Attributes:
        pipeline_id: The identifier of the pipeline this entry
            concerns
        status: The pipeline's current state, as a plain string
        current_stage: The identifier of the stage currently
            running, or None if the pipeline has no stage running
        progress: A best-effort completion fraction between 0.0 and
            1.0
        started_at: When the pipeline's currently running stage
            began, or None if none is running
    """

    pipeline_id: str

    status: str

    current_stage: str

    progress: float

    started_at: datetime

    def __post_init__(self):
        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError(
                "Cannot build a pipeline dashboard entry with an empty or blank pipeline ID."
            )

        if self.status is None or not self.status.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError(
                "Cannot build a pipeline dashboard entry with an empty or blank status."
            )

        if self.current_stage is not None and not self.current_stage.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError(
                "Cannot build a pipeline dashboard entry with a blank current_stage; omit it (None) instead."
            )

        if (
            self.progress is None
            or isinstance(self.progress, bool)
            or not isinstance(self.progress, (int, float))
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError(
                "Cannot build a pipeline dashboard entry with a non-numeric progress."
            )

        if not (0.0 <= self.progress <= 1.0):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError(
                f"Cannot build a pipeline dashboard entry with progress {self.progress!r}; progress must "
                "be between 0.0 and 1.0."
            )
