from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService:
    """
    Organizes consumer projection execution capability registry event
    subscription lifecycle policy profile bindings, binding
    templates, binding presets, and binding groups into isolated
    editing environments (binding workspaces) prior to release.

    The service's responsibility is workspace creation, update,
    cloning, snapshot generation, removal, lookup, and listing, not
    binding creation, binding template creation, binding preset
    creation, binding group creation, profile validation, policy
    evaluation, persistence, logging, or event publication. It does
    NOT create bindings, binding templates, binding presets, or
    binding groups, validate profiles, evaluate policies, persist
    workspaces, log, or publish events. Every mutation produces a
    new, immutable workspace record; no workspace record is ever
    mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two registered workspaces may share a
      workspace ID
    - Order-preserving: Workspaces are listed in the order they were
      first created, and each workspace's member resources are
      listed in the order they were added to it
    - Independent on clone: A cloned workspace is a distinct
      workspace record; updating the original workspace after
      cloning does not affect the clone, and vice versa
    """

    def __init__(self, binding_service, template_service, preset_service, group_service):
        """
        Args:
            binding_service: The service used to verify a binding
                exists before it is referenced by a workspace. Any
                object exposing `contains(binding_id)` is accepted
            template_service: The service used to verify a binding
                template exists before it is referenced by a
                workspace. Any object exposing `contains(template_id)`
                is accepted
            preset_service: The service used to verify a binding
                preset exists before it is referenced by a workspace.
                Any object exposing `contains(preset_id)` is accepted
            group_service: The service used to verify a binding group
                exists before it is referenced by a workspace. Any
                object exposing `contains(group_id)` is accepted
        """

        if binding_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                "Cannot initialize binding workspace service with a None binding service."
            )

        if template_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                "Cannot initialize binding workspace service with a None binding template service."
            )

        if preset_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                "Cannot initialize binding workspace service with a None binding preset service."
            )

        if group_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                "Cannot initialize binding workspace service with a None binding group service."
            )

        self._binding_service = binding_service
        self._template_service = template_service
        self._preset_service = preset_service
        self._group_service = group_service

        self._workspaces = {}
        self._workspace_order = []
        self._lock = RLock()

    def create(
        self,
        workspace: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace:
        """
        Create a binding workspace.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError:
                If the workspace is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
                its workspace ID is already registered, or any of its
                referenced resources is unknown
        """

        self._validate_workspace(workspace)

        with self._lock:
            if workspace.workspace_id in self._workspaces:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                    f"Cannot create a binding workspace: workspace ID {workspace.workspace_id!r} is already registered."
                )

            self._validate_references(workspace)

            self._workspaces[workspace.workspace_id] = workspace
            self._workspace_order.append(workspace.workspace_id)

            return workspace

    def update(
        self,
        workspace: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace:
        """
        Update an already-registered binding workspace.

        The updated workspace keeps its original position in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError:
                If the workspace is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
                no workspace is registered under its workspace ID, or
                any of its referenced resources is unknown
        """

        self._validate_workspace(workspace)

        with self._lock:
            if workspace.workspace_id not in self._workspaces:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                    f"Cannot update a binding workspace: no workspace is registered under workspace ID {workspace.workspace_id!r}."
                )

            self._validate_references(workspace)

            self._workspaces[workspace.workspace_id] = workspace

            return workspace

    def clone(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace:
        """
        Clone the workspace registered under a workspace ID.

        The clone is registered under a newly generated, unique
        workspace ID and carries an independent copy of the original
        workspace's name, description, and referenced resources.
        Updating the original workspace after cloning does not
        affect the clone, and vice versa.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError:
                If the workspace ID is None or blank, or no workspace
                is registered under it
        """

        self._validate_workspace_id(workspace_id)

        with self._lock:
            original = self._workspaces.get(workspace_id)

            if original is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                    f"Cannot clone a binding workspace: no workspace is registered under workspace ID {workspace_id!r}."
                )

            cloned_workspace_id = self._generate_clone_id(workspace_id)

            cloned = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace(
                workspace_id=cloned_workspace_id,
                name=original.name,
                description=original.description,
                binding_ids=original.binding_ids,
                template_ids=original.template_ids,
                preset_ids=original.preset_ids,
                group_ids=original.group_ids,
            )

            self._workspaces[cloned_workspace_id] = cloned
            self._workspace_order.append(cloned_workspace_id)

            return cloned

    def snapshot(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSnapshot:
        """
        Take a snapshot of a workspace's current state.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError:
                If the workspace ID is None or blank, or no workspace
                is registered under it

        Returns:
            An immutable snapshot carrying the workspace's resource
            counts at the moment of the snapshot
        """

        self._validate_workspace_id(workspace_id)

        with self._lock:
            workspace = self._workspaces.get(workspace_id)

            if workspace is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                    f"Cannot snapshot a binding workspace: no workspace is registered under workspace ID {workspace_id!r}."
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSnapshot(
                workspace_id=workspace.workspace_id,
                created_at=datetime.now(timezone.utc),
                resource_counts=MappingProxyType(
                    {
                        "bindings": len(workspace.binding_ids),
                        "templates": len(workspace.template_ids),
                        "presets": len(workspace.preset_ids),
                        "groups": len(workspace.group_ids),
                    }
                ),
            )

    def delete(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace:
        """
        Delete the workspace registered under a workspace ID.

        Unlike a plain deletion, deleting a workspace ID that was
        never registered is rejected rather than treated as a no-op.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError:
                If the workspace ID is None or blank, or no workspace
                is registered under it
        """

        self._validate_workspace_id(workspace_id)

        with self._lock:
            if workspace_id not in self._workspaces:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                    f"Cannot delete a binding workspace: no workspace is registered under workspace ID {workspace_id!r}."
                )

            workspace = self._workspaces.pop(workspace_id)
            self._workspace_order.remove(workspace_id)

            return workspace

    def find(self, workspace_id: str):
        """
        Find the workspace registered under a workspace ID.

        Returns:
            The matching workspace, or None if no workspace is
            registered under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError:
                If the workspace ID is None or blank
        """

        self._validate_workspace_id(workspace_id)

        with self._lock:
            return self._workspaces.get(workspace_id)

    def list(self) -> tuple:
        """
        List every registered workspace, in deterministic order.

        Returns:
            An immutable tuple of every registered workspace,
            preserving creation order
        """

        with self._lock:
            return tuple(self._workspaces[workspace_id] for workspace_id in self._workspace_order)

    def _generate_clone_id(self, workspace_id: str) -> str:
        candidate = f"{workspace_id}-clone"
        suffix = 2

        while candidate in self._workspaces:
            candidate = f"{workspace_id}-clone-{suffix}"
            suffix += 1

        return candidate

    def _validate_references(
        self,
        workspace: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ) -> None:
        for binding_id in workspace.binding_ids:
            if not self._binding_service.contains(binding_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                    f"Cannot save a binding workspace: no binding is registered under binding ID {binding_id!r}."
                )

        for template_id in workspace.template_ids:
            if not self._template_service.contains(template_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                    f"Cannot save a binding workspace: no binding template is registered under template ID {template_id!r}."
                )

        for preset_id in workspace.preset_ids:
            if not self._preset_service.contains(preset_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                    f"Cannot save a binding workspace: no binding preset is registered under preset ID {preset_id!r}."
                )

        for group_id in workspace.group_ids:
            if not self._group_service.contains(group_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                    f"Cannot save a binding workspace: no binding group is registered under group ID {group_id!r}."
                )

    def _validate_workspace_id(self, workspace_id) -> None:
        if workspace_id is None or not workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                "Cannot operate on a binding workspace with an empty or blank workspace ID."
            )

    def _validate_workspace(self, workspace) -> None:
        if workspace is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                "Cannot save a None binding workspace."
            )

        if not isinstance(
            workspace,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceError(
                "Cannot save a binding workspace: workspace must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace."
            )

        self._validate_workspace_id(workspace.workspace_id)
