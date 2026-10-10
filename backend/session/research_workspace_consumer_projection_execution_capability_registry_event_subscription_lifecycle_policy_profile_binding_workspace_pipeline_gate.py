from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_gate_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_gate_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus,
)

VALID_GATE_TYPES = (
    "manual",
    "automatic",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate:
    """
    Immutable definition of an approval checkpoint a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace pipeline stage must
    clear before it may run.

    The gate is a value object only. It performs no evaluation, and
    no transition. Evaluation and transition are the responsibility
    of a pipeline gate service.

    Attributes:
        gate_id: The gate's unique identifier
        stage_id: The identifier of the stage the gate guards; a
            stage may have at most one gate
        gate_type: How the gate is resolved, either "manual" (an
            explicit open() or close() call is required) or
            "automatic" (opened automatically the first time it is
            evaluated)
        status: The gate's current state
        mandatory: Whether the gate may never be bypassed; a
            mandatory gate must be explicitly opened or closed
    """

    gate_id: str

    stage_id: str

    gate_type: str

    status: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus = field(
        default=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus.PENDING
    )

    mandatory: bool = True

    def __post_init__(self):
        if self.gate_id is None or not self.gate_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot build a pipeline gate with an empty or blank gate ID."
            )

        if self.stage_id is None or not self.stage_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot build a pipeline gate with an empty or blank stage ID."
            )

        if self.gate_type not in VALID_GATE_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                f"Invalid pipeline gate type {self.gate_type!r}. Must be one of {VALID_GATE_TYPES!r}."
            )

        if not isinstance(self.status, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot build a pipeline gate: status must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus."
            )

        if not isinstance(self.mandatory, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError(
                "Cannot build a pipeline gate with a non-boolean mandatory flag."
            )
