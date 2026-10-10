from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError,
)

_VALID_OPERATION_TYPES = (
    "add",
    "remove",
)

_VALID_RESOURCE_TYPES = (
    "binding",
    "template",
    "preset",
    "group",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation:
    """
    Immutable description of a single staged edit to a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace's member resources.

    The operation is a value object only. It performs no application
    against a workspace. Staging, ordering, and application of
    operations are the responsibility of a binding workspace change
    set and a binding workspace change set service.

    Attributes:
        operation_id: The operation's unique identifier
        operation_type: The kind of edit the operation stages (one of
            "add" or "remove")
        resource_type: The kind of member resource the operation
            concerns (one of "binding", "template", "preset", or
            "group")
        resource_id: The identifier of the member resource the
            operation concerns
        payload: Optional, operation-specific metadata, or None if
            the operation carries none
    """

    operation_id: str

    operation_type: str

    resource_type: str

    resource_id: str

    payload: (
        Mapping | None
    ) = None

    def __post_init__(self):
        if self.operation_id is None or not self.operation_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change operation with an empty or blank operation ID."
            )

        if self.operation_type is None or not self.operation_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change operation with an empty or blank operation type."
            )

        if self.operation_type not in _VALID_OPERATION_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                f"Invalid change operation type {self.operation_type!r}. Must be one of {_VALID_OPERATION_TYPES!r}."
            )

        if self.resource_type is None or not self.resource_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change operation with an empty or blank resource type."
            )

        if self.resource_type not in _VALID_RESOURCE_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                f"Invalid change operation resource type {self.resource_type!r}. Must be one of {_VALID_RESOURCE_TYPES!r}."
            )

        if self.resource_id is None or not self.resource_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change operation with an empty or blank resource ID."
            )

        if self.payload is not None and not isinstance(self.payload, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change operation with a payload that is not a mapping."
            )
