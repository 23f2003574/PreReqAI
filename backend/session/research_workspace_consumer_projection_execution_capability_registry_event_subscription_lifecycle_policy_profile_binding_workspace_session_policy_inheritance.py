from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_inheritance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError,
)

VALID_SESSION_POLICY_INHERITANCE_FIELDS = (
    "name",
    "max_runtime",
    "max_idle",
    "allow_restore",
    "enabled",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritance:
    """
    Immutable record linking one consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session policy as the single parent
    of another, so the child may reuse the parent's configuration
    while selectively overriding specific fields.

    The inheritance link is a value object only. It performs no
    resolution or cycle detection. Linking, unlinking, and resolving
    the effective, merged configuration of a policy are the
    responsibility of a session policy inheritance service.

    Attributes:
        child_policy_id: The identifier of the policy that inherits
            from parent_policy_id
        parent_policy_id: The identifier of the policy child_policy_id
            inherits from
        overridden_fields: Which of the child's fields take the
            child's own value instead of the parent's, a subset of
            "name", "max_runtime", "max_idle", "allow_restore", and
            "enabled"
    """

    child_policy_id: str

    parent_policy_id: str

    overridden_fields: tuple[str, ...]

    def __post_init__(self):
        if self.child_policy_id is None or not self.child_policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                "Cannot build a session policy inheritance link with an empty or blank child policy ID."
            )

        if self.parent_policy_id is None or not self.parent_policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                "Cannot build a session policy inheritance link with an empty or blank parent policy ID."
            )

        if self.child_policy_id == self.parent_policy_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                f"Cannot build a session policy inheritance link where policy ID {self.child_policy_id!r} is its "
                "own parent."
            )

        if self.overridden_fields is None or not isinstance(self.overridden_fields, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                "Cannot build a session policy inheritance link with overridden_fields that is not a tuple."
            )

        for field_name in self.overridden_fields:
            if field_name not in VALID_SESSION_POLICY_INHERITANCE_FIELDS:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                    f"Invalid session policy inheritance overridden field {field_name!r}. Must be one of "
                    f"{VALID_SESSION_POLICY_INHERITANCE_FIELDS!r}."
                )
