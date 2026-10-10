from dataclasses import (
    dataclass,
    field,
)

from types import MappingProxyType

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_pipeline_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError,
)

VALID_PIPELINE_STAGE_TYPES = (
    "validation",
    "review",
    "merge",
    "deployment",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage:
    """
    Immutable definition of a single step of a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution pipeline.

    The stage is a value object only. It performs no execution. Its
    type names which stage executor an execution pipeline service
    dispatches it to when its pipeline runs: "validation", "review",
    "merge", or "deployment".

    Attributes:
        stage_id: The stage's unique identifier within its pipeline
        type: The kind of operation the stage performs, one of
            "validation", "review", "merge", or "deployment"
        order: The stage's position in its pipeline's execution
            sequence; must be unique among a pipeline's stages
        configuration: The keyword arguments passed to the stage
            type's executor when the stage runs, empty if none apply
    """

    stage_id: str

    type: str

    order: int

    configuration: Mapping = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self):
        if self.stage_id is None or not self.stage_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                "Cannot build a pipeline stage with an empty or blank stage ID."
            )

        if self.type is None or not self.type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                "Cannot build a pipeline stage with an empty or blank type."
            )

        if self.type not in VALID_PIPELINE_STAGE_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                f"Invalid pipeline stage type {self.type!r}. Must be one of {VALID_PIPELINE_STAGE_TYPES!r}."
            )

        if not isinstance(self.order, int) or isinstance(self.order, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                "Cannot build a pipeline stage with a non-integer order."
            )

        if self.order < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                "Cannot build a pipeline stage with a negative order."
            )

        if self.configuration is None or not isinstance(self.configuration, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                "Cannot build a pipeline stage with configuration that is not a mapping."
            )
