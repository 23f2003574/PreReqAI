from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_observability_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError,
)

VALID_TRACE_STATUSES = (
    "running",
    "succeeded",
    "failed",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionTrace:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution pipeline stage's execution, kept for
    timing and diagnostics, independent of the pipeline's own
    execution flow.

    The trace is a value object only. It performs no timing and no
    recording. Timing and recording are the responsibility of a
    pipeline observability service.

    Attributes:
        trace_id: The trace's unique identifier
        pipeline_id: The identifier of the pipeline the traced stage
            belongs to
        stage_id: The identifier of the traced stage
        started_at: When the stage began running
        finished_at: When the stage stopped running; None while the
            stage is still running
        status: The trace's current state: "running" while in
            progress, "succeeded" or "failed" once finished
    """

    trace_id: str

    pipeline_id: str

    stage_id: str

    started_at: datetime

    finished_at: datetime

    status: str

    def __post_init__(self):
        if self.trace_id is None or not self.trace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline execution trace with an empty or blank trace ID."
            )

        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline execution trace with an empty or blank pipeline ID."
            )

        if self.stage_id is None or not self.stage_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline execution trace with an empty or blank stage ID."
            )

        if self.started_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline execution trace with a None started_at."
            )

        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline execution trace with a finished_at earlier than started_at."
            )

        if self.status not in VALID_TRACE_STATUSES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                f"Invalid pipeline execution trace status {self.status!r}. Must be one of "
                f"{VALID_TRACE_STATUSES!r}."
            )

        if self.status == "running" and self.finished_at is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline execution trace: a running trace must not have a finished_at."
            )

        if self.status != "running" and self.finished_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline execution trace: a finished trace must have a finished_at."
            )
