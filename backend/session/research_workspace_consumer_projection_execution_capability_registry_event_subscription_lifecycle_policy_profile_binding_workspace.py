from dataclasses import (
    dataclass,
)


from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace:
    """
    Immutable record describing an isolated editing environment that
    organizes consumer projection execution capability registry
    event subscription lifecycle policy profile bindings, binding
    templates, binding presets, and binding groups together before
    they are released.

    The workspace is a value object only. It performs no creation,
    no update, no cloning, and no snapshot generation. Creation,
    update, cloning, snapshot generation, removal, lookup, and
    listing are the responsibility of a binding workspace service,
    which produces a new workspace record for every change rather
    than mutating an existing one.

    Attributes:
        workspace_id: The workspace's unique identifier
        name: The workspace's human-readable name
        description: A human-readable description of the workspace
        binding_ids: The identifiers of the workspace's member
            bindings, in deterministic order
        template_ids: The identifiers of the workspace's member
            binding templates, in deterministic order
        preset_ids: The identifiers of the workspace's member
            binding presets, in deterministic order
        group_ids: The identifiers of the workspace's member binding
            groups, in deterministic order
    """

    workspace_id: str

    name: str

    description: str | None

    binding_ids: tuple

    template_ids: tuple

    preset_ids: tuple

    group_ids: tuple

    def __post_init__(self):
        if self.workspace_id is None or not self.workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                "Cannot build a binding workspace with an empty or blank workspace ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                "Cannot build a binding workspace with an empty or blank name."
            )

        self._validate_member_ids(self.binding_ids, "binding")
        self._validate_member_ids(self.template_ids, "binding template")
        self._validate_member_ids(self.preset_ids, "binding preset")
        self._validate_member_ids(self.group_ids, "binding group")

    def _validate_member_ids(self, member_ids, label: str) -> None:
        if member_ids is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                f"Cannot build a binding workspace with None {label} IDs."
            )

        for member_id in member_ids:
            if member_id is None or not member_id.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                    f"Cannot build a binding workspace with an empty or blank member {label} ID."
                )

        if len(set(member_ids)) != len(member_ids):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                f"Cannot build a binding workspace with duplicate member {label} IDs."
            )
