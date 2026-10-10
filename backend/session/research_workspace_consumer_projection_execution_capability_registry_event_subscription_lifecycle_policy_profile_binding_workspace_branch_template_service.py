from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_protection_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_template import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplate,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_template_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateAssignment,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_template_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateService:
    """
    Registers reusable protection, review, and synchronization policy
    bundles (templates) for consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace branches, and assigns or unassigns them to branches for
    consistent workflows.

    The service's responsibility is template registration and
    assignment tracking, not branch creation, checkout, renaming,
    closing, or archiving themselves, or change set, review, conflict,
    or synchronization management. It does NOT create, checkout,
    rename, close, or archive a branch, or create, stage, or review
    change sets. Assigning a template only applies its
    protection_policy (through a branch protection service's
    protect()) and, when its sync_policy requests it, triggers a
    best-effort synchronization (through a branch synchronization
    service's sync()); it never touches the branch's own workspace,
    name, revisions, or status, so a branch's existing history from
    every other service is entirely unaffected by template assignment
    or unassignment. review_policy is not enforced directly — a branch
    review service (commit #2) uses a single, service-wide approval
    policy fixed at construction, so a template's review_policy is
    retained as reference data for whoever constructs the review
    workflow for that branch, rather than applied automatically.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two registered templates may share a
      template ID or a name
    - Single-assignment: A branch may have at most one template
      assigned at a time; assigning a second template while one is
      already assigned is rejected until the first is unassigned
    - Symmetric: Unassigning a template removes the protection it
      applied, returning the branch to unprotected, just as assigning
      it applied that protection
    - Non-destructive: Registering, assigning, or unassigning a
      template never mutates a branch's own state or any other
      service's history
    """

    def __init__(self, branch_service, protection_service, sync_service):
        """
        Args:
            branch_service: The service used to verify a branch
                exists before a template is assigned or unassigned.
                Any object exposing `find(branch_id)` is accepted
            protection_service: The service used to apply and remove a
                template's protection policy. Any object exposing
                `protect(branch_id, allow_direct_changes,
                require_review, require_clean_merge)` and
                `unprotect(branch_id)` is accepted
            sync_service: The service used to best-effort synchronize
                a branch when a template's sync_policy requests it.
                Any object exposing `sync(branch_id)` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError:
                If branch_service, protection_service, or sync_service
                is None
        """

        for dependency, name in (
            (branch_service, "branch service"),
            (protection_service, "branch protection service"),
            (sync_service, "branch synchronization service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                    f"Cannot initialize branch template service with a None {name}."
                )

        self._branch_service = branch_service
        self._protection_service = protection_service
        self._sync_service = sync_service
        self._templates = {}
        self._templates_by_name = {}
        self._template_order = []
        self._assignments = {}
        self._lock = RLock()

    def register(
        self,
        template: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplate,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplate:
        """
        Register a reusable branch template.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError:
                If template is None or not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplate,
                its template ID is already registered, or its name is
                already used by another registered template
        """

        if template is None or not isinstance(
            template,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplate,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                "Cannot register a template: template must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplate."
            )

        with self._lock:
            if template.template_id in self._templates:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                    f"Cannot register a template: template ID {template.template_id!r} is already registered."
                )

            if template.name in self._templates_by_name:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                    f"Cannot register a template: name {template.name!r} is already used by another template."
                )

            self._templates[template.template_id] = template
            self._templates_by_name[template.name] = template.template_id
            self._template_order.append(template.template_id)

            return template

    def assign(
        self,
        branch_id: str,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateAssignment:
        """
        Assign a registered template to a branch, applying its
        protection policy and, if requested, triggering a
        best-effort synchronization.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError:
                If branch_id or template_id is None or blank, no
                branch is registered under branch_id, no template is
                registered under template_id, or the branch already
                has a template assigned
        """

        self._validate_id(branch_id, "branch ID")
        self._validate_id(template_id, "template ID")

        with self._lock:
            self._resolve_branch(branch_id)
            template = self._resolve_template(template_id)

            existing = self._assignments.get(branch_id)

            if existing is not None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                    f"Cannot assign template ID {template_id!r} to branch ID {branch_id!r}: it already has "
                    f"template ID {existing.template_id!r} assigned; unassign it first."
                )

            self._protection_service.protect(
                branch_id,
                allow_direct_changes=template.protection_policy["allow_direct_changes"],
                require_review=template.protection_policy["require_review"],
                require_clean_merge=template.protection_policy["require_clean_merge"],
            )

            if template.sync_policy["auto_sync"]:
                try:
                    self._sync_service.sync(branch_id)
                except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError:
                    pass

            assignment = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateAssignment(
                branch_id=branch_id,
                template_id=template_id,
                assigned_at=datetime.now(timezone.utc),
            )

            self._assignments[branch_id] = assignment

            return assignment

    def unassign(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateAssignment:
        """
        Unassign a branch's currently assigned template, removing the
        protection it applied.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError:
                If branch_id is None or blank, no branch is registered
                under it, or it has no template currently assigned
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            self._resolve_branch(branch_id)

            if branch_id not in self._assignments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                    f"Cannot unassign: branch ID {branch_id!r} has no template currently assigned."
                )

            try:
                self._protection_service.unprotect(branch_id)
            except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionError:
                pass

            return self._assignments.pop(branch_id)

    def template(self, branch_id: str):
        """
        Find the template currently assigned to a branch.

        Returns:
            The assigned template, or None if the branch has no
            template currently assigned

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError:
                If branch_id is None or blank, or no branch is
                registered under it
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            self._resolve_branch(branch_id)

            assignment = self._assignments.get(branch_id)

            if assignment is None:
                return None

            return self._templates[assignment.template_id]

    def list(self) -> tuple:
        """
        List every registered template, in registration order.
        """

        with self._lock:
            return tuple(self._templates[template_id] for template_id in self._template_order)

    def find(self, template_id: str):
        """
        Find the template registered under a template ID.

        Returns:
            The matching template, or None if no template is
            registered under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError:
                If template_id is None or blank
        """

        self._validate_id(template_id, "template ID")

        with self._lock:
            return self._templates.get(template_id)

    def _resolve_branch(self, branch_id: str):
        branch = self._branch_service.find(branch_id)

        if branch is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                f"Cannot operate on a branch template: no branch is registered under branch ID {branch_id!r}."
            )

        return branch

    def _resolve_template(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplate:
        template = self._templates.get(template_id)

        if template is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                f"Cannot operate on a branch template: no template is registered under template ID {template_id!r}."
            )

        return template

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTemplateError(
                f"Cannot operate on a branch template with an empty or blank {label}."
            )
