from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime

from types import MappingProxyType

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_event_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError,
)

VALID_PIPELINE_EVENT_TYPES = (
    "stage_started",
    "stage_completed",
    "stage_failed",
    "stage_paused",
    "stage_cancelled",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEvent:
    """
    Immutable record of a single lifecycle occurrence published by a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace
    execution pipeline, kept for delivery to interested subscribers.

    The event is a value object only. It performs no publication and
    no delivery. Publication and delivery are the responsibility of a
    pipeline event bus.

    Attributes:
        event_id: The event's unique identifier
        pipeline_id: The identifier of the pipeline the event
            concerns
        stage_id: The identifier of the stage the event concerns
        event_type: The kind of lifecycle occurrence this event
            captures, one of "stage_started", "stage_completed",
            "stage_failed", "stage_paused", or "stage_cancelled"
        timestamp: When the occurrence happened
        payload: Structured, event-specific details, empty if none
            apply
    """

    event_id: str

    pipeline_id: str

    stage_id: str

    event_type: str

    timestamp: datetime

    payload: Mapping = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self):
        if self.event_id is None or not self.event_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot build a pipeline event with an empty or blank event ID."
            )

        if self.pipeline_id is None or not self.pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot build a pipeline event with an empty or blank pipeline ID."
            )

        if self.stage_id is None or not self.stage_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot build a pipeline event with an empty or blank stage ID."
            )

        if self.event_type is None or not self.event_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot build a pipeline event with an empty or blank event type."
            )

        if self.event_type not in VALID_PIPELINE_EVENT_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                f"Invalid pipeline event type {self.event_type!r}. Must be one of "
                f"{VALID_PIPELINE_EVENT_TYPES!r}."
            )

        if self.timestamp is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot build a pipeline event with a None timestamp."
            )

        if self.payload is None or not isinstance(self.payload, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError(
                "Cannot build a pipeline event with a payload that is not a mapping."
            )
