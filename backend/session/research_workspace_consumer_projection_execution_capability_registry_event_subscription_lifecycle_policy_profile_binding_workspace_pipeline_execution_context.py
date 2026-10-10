from dataclasses import (
    dataclass,
    field,
)

from types import MappingProxyType

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_execution_context_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContext:
    """
    Immutable snapshot of the shared key/value state a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution pipeline's
    stages exchange, so one stage can hand state to a later stage
    without either knowing about the other.

    The context is a value object only. It performs no reads, no
    writes, and no propagation. Reads, writes, and propagation are
    the responsibility of a pipeline context service.

    Attributes:
        context_id: The context's unique identifier
        pipeline_id: The identifier of the pipeline the context
            belongs to
        variables: The context's current shared key/value state
        metadata: Descriptive, non-shared details about the context,
            empty if none apply
    """

    context_id: str

    pipeline_id: str

    variables: Mapping = field(default_factory=lambda: MappingProxyType({}))

    metadata: Mapping = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self):
        if self.context_id is None or not self.context_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                "Cannot build a pipeline execution context with an empty or blank context ID."
            )

        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                "Cannot build a pipeline execution context with an empty or blank pipeline ID."
            )

        if self.variables is None or not isinstance(self.variables, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                "Cannot build a pipeline execution context with variables that are not a mapping."
            )

        if self.metadata is None or not isinstance(self.metadata, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                "Cannot build a pipeline execution context with metadata that is not a mapping."
            )
