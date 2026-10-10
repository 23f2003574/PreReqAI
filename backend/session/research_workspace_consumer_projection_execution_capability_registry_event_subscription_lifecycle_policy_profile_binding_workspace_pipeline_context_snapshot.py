from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime

from types import MappingProxyType

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_execution_context_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineContextSnapshot:
    """
    Immutable checkpoint of a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace pipeline execution context's state at a single
    point in time.

    The snapshot is a value object only. It performs no capture and
    no restoration. Capture and restoration are the responsibility of
    a pipeline context service. Once constructed, a snapshot's
    captured state can never change.

    Attributes:
        snapshot_id: The snapshot's unique identifier
        context_id: The identifier of the context this snapshot was
            captured from
        stage_id: The identifier of the stage that triggered the
            checkpoint, if known; None if not associated with a
            specific stage
        created_at: When the snapshot was captured
        variables: The context's variables at capture time
        metadata: The context's metadata at capture time
    """

    snapshot_id: str

    context_id: str

    stage_id: str

    created_at: datetime

    variables: Mapping = field(default_factory=lambda: MappingProxyType({}))

    metadata: Mapping = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self):
        if self.snapshot_id is None or not self.snapshot_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                "Cannot build a pipeline context snapshot with an empty or blank snapshot ID."
            )

        if self.context_id is None or not self.context_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                "Cannot build a pipeline context snapshot with an empty or blank context ID."
            )

        if self.stage_id is not None and not self.stage_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                "Cannot build a pipeline context snapshot with a blank stage ID; omit it (None) instead."
            )

        if self.created_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                "Cannot build a pipeline context snapshot with a None created_at."
            )

        if self.variables is None or not isinstance(self.variables, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                "Cannot build a pipeline context snapshot with variables that are not a mapping."
            )

        if self.metadata is None or not isinstance(self.metadata, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                "Cannot build a pipeline context snapshot with metadata that are not a mapping."
            )
