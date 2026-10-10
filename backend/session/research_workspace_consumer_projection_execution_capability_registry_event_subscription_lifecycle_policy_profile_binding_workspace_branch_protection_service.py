from threading import (
    RLock,
)

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_protection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_protection_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_protection_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionResult,
)

_VALID_OPERATION_TYPES = (
    "direct_edit",
    "merge",
    "delete",
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionService:
    """
    Enforces edit, merge, and deletion rules on protected consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace branches, so changes
    to important branches are caught before they reach deployment.

    The service's responsibility is applying, removing, and
    evaluating protection rules, not branch creation, checkout,
    renaming, closing, change set creation, review, merging, or
    rebasing themselves. It does NOT create, checkout, rename, or
    close a branch, create or stage change sets, approve or reject
    reviews, merge, or rebase. It operates over a branch service
    supplied at construction time only to verify a branch exists;
    every attempted operation is described by the caller, so it
    integrates with the change set, review, merge, and rebase
    workflows without depending on any of them directly — a caller
    checks a change set's approval and conflict state through those
    services and passes the result along in the operation it asks
    this service to validate.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Inert when unprotected: Every operation is permitted on a branch
      that is not currently protected, or has never been protected
    - Non-raising on rule violation: validate_operation() reports
      violations in its result rather than raising; only malformed
      input, an unknown branch, or an unrecognized operation type
      raises
    - Absolute on deletion: A protected branch can never be deleted,
      regardless of its other rules
    - Current-state-only: protect() and unprotect() replace a
      branch's protection rules outright; no history of prior rule
      sets is retained
    """

    def __init__(self, branch_service):
        """
        Args:
            branch_service: The service used to verify a branch
                exists before its protection rules are applied,
                removed, or evaluated. Any object exposing
                `find(branch_id)` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError:
                If branch_service is None
        """

        if branch_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError(
                "Cannot initialize branch protection service with a None branch service."
            )

        self._branch_service = branch_service
        self._protections = {}
        self._lock = RLock()

    def protect(
        self,
        branch_id: str,
        allow_direct_changes: bool = False,
        require_review: bool = True,
        require_clean_merge: bool = True,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtection:
        """
        Protect a branch, replacing any protection rules already
        applied to it.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError:
                If branch_id is None or blank, no branch is registered
                under it, or allow_direct_changes and require_review
                are both True
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            self._resolve_branch(branch_id)

            protection = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtection(
                branch_id=branch_id,
                protected=True,
                allow_direct_changes=allow_direct_changes,
                require_review=require_review,
                require_clean_merge=require_clean_merge,
            )

            self._protections[branch_id] = protection

            return protection

    def unprotect(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtection:
        """
        Remove protection from a branch. Calling this on a branch
        that is not currently protected is a no-op that still returns
        its (already unprotected) rules.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError:
                If branch_id is None or blank, or no branch is
                registered under it
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            self._resolve_branch(branch_id)

            protection = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtection(
                branch_id=branch_id,
                protected=False,
                allow_direct_changes=True,
                require_review=False,
                require_clean_merge=False,
            )

            self._protections[branch_id] = protection

            return protection

    def validate_operation(
        self,
        branch_id: str,
        operation: Mapping,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionResult:
        """
        Evaluate an attempted operation against a branch's current
        protection rules.

        Args:
            branch_id: The branch the operation targets
            operation: A mapping describing the attempted operation.
                Must carry a "type" key of "direct_edit", "merge", or
                "delete". A "merge" operation may carry "approved"
                (whether every change set being merged is currently
                approved) and "clean" (whether the merge is free of
                unresolved conflicts); both default to False when
                omitted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError:
                If branch_id is None or blank, no branch is registered
                under it, operation is None or not a mapping, or its
                "type" is missing or not "direct_edit", "merge", or
                "delete"
        """

        self._validate_id(branch_id, "branch ID")
        operation_type = self._validate_operation(operation)

        with self._lock:
            self._resolve_branch(branch_id)

            protection = self._current_protection(branch_id)

            violations = []

            if protection.protected:
                if operation_type == "direct_edit" and not protection.allow_direct_changes:
                    violations.append(
                        f"Direct changes are not allowed on protected branch ID {branch_id!r}."
                    )
                elif operation_type == "merge":
                    if protection.require_review and not operation.get("approved", False):
                        violations.append(
                            f"Merging into protected branch ID {branch_id!r} requires every change set to be "
                            "approved first."
                        )

                    if protection.require_clean_merge and not operation.get("clean", False):
                        violations.append(
                            f"Merging into protected branch ID {branch_id!r} requires a clean, conflict-free "
                            "result."
                        )
                elif operation_type == "delete":
                    violations.append(f"Protected branch ID {branch_id!r} cannot be deleted.")

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionResult(
                permitted=not violations,
                violations=tuple(violations),
            )

    def status(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtection:
        """
        Look up a branch's current protection rules.

        A branch that has never been protected reports back a fully
        open, unprotected rule set rather than None.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError:
                If branch_id is None or blank, or no branch is
                registered under it
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            self._resolve_branch(branch_id)

            return self._current_protection(branch_id)

    def _current_protection(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtection:
        existing = self._protections.get(branch_id)

        if existing is not None:
            return existing

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtection(
            branch_id=branch_id,
            protected=False,
            allow_direct_changes=True,
            require_review=False,
            require_clean_merge=False,
        )

    def _resolve_branch(self, branch_id: str):
        branch = self._branch_service.find(branch_id)

        if branch is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError(
                f"Cannot operate on a branch protection: no branch is registered under branch ID {branch_id!r}."
            )

        return branch

    def _validate_operation(self, operation: Mapping) -> str:
        if operation is None or not isinstance(operation, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError(
                "Cannot validate an operation that is None or not a mapping."
            )

        operation_type = operation.get("type")

        if operation_type not in _VALID_OPERATION_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError(
                f"Cannot validate an operation with an unrecognized type {operation_type!r}. Must be one of "
                f"{_VALID_OPERATION_TYPES!r}."
            )

        return operation_type

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError(
                f"Cannot operate on a branch protection with an empty or blank {label}."
            )
