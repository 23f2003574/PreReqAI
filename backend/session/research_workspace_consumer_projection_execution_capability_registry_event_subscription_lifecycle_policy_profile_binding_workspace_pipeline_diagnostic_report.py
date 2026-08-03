from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_observability_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDiagnosticReport:
    """
    Immutable diagnostic summary generated from a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace execution pipeline's completed
    and in-progress execution traces.

    The report is a value object only. It performs no aggregation.
    Aggregation is the responsibility of a pipeline observability
    service.

    Attributes:
        pipeline_id: The identifier of the pipeline this report
            concerns
        duration: The total time, in seconds, spent across the
            pipeline's finished stage traces
        failed_stage: The identifier of the first stage whose trace
            failed, or None if none has
        warnings: Human-readable notices about the pipeline's traces,
            for example a stage that never finished; empty if none
            apply
    """

    pipeline_id: str

    duration: float

    failed_stage: str

    warnings: tuple = field(default_factory=tuple)

    def __post_init__(self):
        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline diagnostic report with an empty or blank pipeline ID."
            )

        if (
            self.duration is None
            or isinstance(self.duration, bool)
            or not isinstance(self.duration, (int, float))
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline diagnostic report with a non-numeric duration."
            )

        if self.duration < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline diagnostic report with a negative duration."
            )

        if self.failed_stage is not None and not self.failed_stage.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline diagnostic report with a blank failed_stage; omit it (None) instead."
            )

        if self.warnings is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot build a pipeline diagnostic report with None warnings."
            )

        for warning in self.warnings:
            if not isinstance(warning, str) or not warning.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                    "Cannot build a pipeline diagnostic report with a blank warning."
                )
