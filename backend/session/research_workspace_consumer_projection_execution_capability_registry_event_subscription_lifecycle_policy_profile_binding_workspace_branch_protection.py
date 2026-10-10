from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_protection_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtection:
    """
    Immutable rule set describing how a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace branch is protected against direct edits,
    unreviewed or conflicted merges, and deletion.

    The protection is a value object only. It performs no
    enforcement. Applying, removing, and evaluating a branch's
    protection rules is the responsibility of a binding workspace
    branch protection service.

    Attributes:
        branch_id: The identifier of the branch the rules apply to
        protected: Whether the branch is currently protected at all;
            when False, every other rule is inert
        allow_direct_changes: Whether edits may bypass the change set
            and review pipeline entirely while the branch is
            protected
        require_review: Whether every change set merged into the
            branch must be approved first
        require_clean_merge: Whether a merge into the branch must be
            free of unresolved conflicts
    """

    branch_id: str

    protected: bool

    allow_direct_changes: bool

    require_review: bool

    require_clean_merge: bool

    def __post_init__(self):
        if self.branch_id is None or not self.branch_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError(
                "Cannot build a branch protection with an empty or blank branch ID."
            )

        for field_name in (
            "protected",
            "allow_direct_changes",
            "require_review",
            "require_clean_merge",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError(
                    f"Cannot build a branch protection: {field_name} must be a bool."
                )

        if self.allow_direct_changes and self.require_review:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError(
                "Cannot build a branch protection with conflicting rules: allow_direct_changes permits edits to "
                "bypass review entirely, which contradicts require_review."
            )
