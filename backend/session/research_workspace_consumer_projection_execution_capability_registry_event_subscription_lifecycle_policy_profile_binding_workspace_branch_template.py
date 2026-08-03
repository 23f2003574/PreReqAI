from dataclasses import (
    dataclass,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_template_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_approval_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy,
)

_PROTECTION_POLICY_KEYS = frozenset(
    {
        "allow_direct_changes",
        "require_review",
        "require_clean_merge",
    }
)

_SYNC_POLICY_KEYS = frozenset(
    {
        "auto_sync",
        "stale_threshold_days",
    }
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplate:
    """
    Immutable, reusable bundle of protection, review, and
    synchronization policies for consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace branches, so teams can apply a consistent
    workflow to many branches at once instead of configuring each one
    individually.

    The template is a value object only. It performs no registration
    or assignment. Registering a template, and assigning or
    unassigning it to a branch, is the responsibility of a binding
    workspace branch template service.

    Attributes:
        template_id: The template's unique identifier
        name: The template's human-readable, globally unique name
        protection_policy: The branch protection rules the template
            applies, as a mapping with boolean "allow_direct_changes",
            "require_review", and "require_clean_merge" keys — the
            same keyword arguments a binding workspace branch
            protection service's protect() accepts
        review_policy: The approval policy the template recommends for
            reviewing change sets against a branch it is assigned to
        sync_policy: The synchronization preferences the template
            applies, as a mapping with a boolean "auto_sync" key and
            an int "stale_threshold_days" key
    """

    template_id: str

    name: str

    protection_policy: Mapping

    review_policy: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy

    sync_policy: Mapping

    def __post_init__(self):
        if self.template_id is None or not self.template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template with an empty or blank template ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template with an empty or blank name."
            )

        self._validate_protection_policy()
        self._validate_review_policy()
        self._validate_sync_policy()

    def _validate_protection_policy(self) -> None:
        if not isinstance(self.protection_policy, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template: protection_policy must be a mapping."
            )

        if set(self.protection_policy.keys()) != _PROTECTION_POLICY_KEYS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                f"Cannot build a branch template: protection_policy must have exactly the keys "
                f"{sorted(_PROTECTION_POLICY_KEYS)!r}."
            )

        for key in _PROTECTION_POLICY_KEYS:
            if not isinstance(self.protection_policy[key], bool):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                    f"Cannot build a branch template: protection_policy[{key!r}] must be a bool."
                )

        if self.protection_policy["allow_direct_changes"] and self.protection_policy["require_review"]:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template with conflicting protection_policy rules: "
                "allow_direct_changes permits edits to bypass review entirely, which contradicts "
                "require_review."
            )

    def _validate_review_policy(self) -> None:
        if not isinstance(
            self.review_policy,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template: review_policy must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy."
            )

    def _validate_sync_policy(self) -> None:
        if not isinstance(self.sync_policy, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template: sync_policy must be a mapping."
            )

        if set(self.sync_policy.keys()) != _SYNC_POLICY_KEYS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                f"Cannot build a branch template: sync_policy must have exactly the keys "
                f"{sorted(_SYNC_POLICY_KEYS)!r}."
            )

        if not isinstance(self.sync_policy["auto_sync"], bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template: sync_policy['auto_sync'] must be a bool."
            )

        stale_threshold_days = self.sync_policy["stale_threshold_days"]

        if (
            not isinstance(stale_threshold_days, int)
            or isinstance(stale_threshold_days, bool)
            or stale_threshold_days < 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot build a branch template: sync_policy['stale_threshold_days'] must be a non-negative int."
            )
