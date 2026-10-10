from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup:
    """
    Immutable record grouping consumer projection execution
    capability registry event subscription lifecycle policy profile
    bindings into a reusable logical unit for bulk management and
    deployment.

    The group is a value object only. It performs no membership
    management. Creation, update, removal, and membership management
    are the responsibility of a binding group service, which produces
    a new group record for every change rather than mutating an
    existing one.

    Attributes:
        group_id: The group's unique identifier
        group_name: The group's human-readable name
        binding_ids: The identifiers of the group's member bindings,
            in deterministic order
    """

    group_id: str

    group_name: str

    binding_ids: tuple

    def __post_init__(self):
        if self.group_id is None or not self.group_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                "Cannot build a binding group with an empty or blank group ID."
            )

        if self.group_name is None or not self.group_name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                "Cannot build a binding group with an empty or blank group name."
            )

        if self.binding_ids is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                "Cannot build a binding group with None binding IDs."
            )

        for binding_id in self.binding_ids:
            if binding_id is None or not binding_id.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                    "Cannot build a binding group with an empty or blank member binding ID."
                )

        if len(set(self.binding_ids)) != len(self.binding_ids):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                "Cannot build a binding group with duplicate member bindings."
            )
