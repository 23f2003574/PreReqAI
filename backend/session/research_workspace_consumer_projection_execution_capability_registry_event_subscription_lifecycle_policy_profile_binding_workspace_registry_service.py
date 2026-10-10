from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_registry_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistrySnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService:
    """
    Maintains a centralised registry of consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspaces, addressed by workspace identifier, for fast
    lookup, replacement, and snapshot generation.

    The service's responsibility is workspace registration,
    replacement, removal, lookup, containment checking, listing, and
    snapshot generation, not workspace creation, binding creation,
    binding template creation, binding preset creation, binding group
    creation, profile validation, policy evaluation, persistence,
    logging, or event publication. It does NOT create workspaces,
    bindings, binding templates, binding presets, or binding groups,
    validate profiles, evaluate policies, persist the registry, log,
    or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two registered workspaces may share a
      workspace ID
    - Order-preserving: Workspaces are listed in the order they were
      first registered
    - Immutable registry: The underlying registry value object is
      replaced atomically on every mutation rather than mutated in
      place
    """

    def __init__(self):
        self._registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistry(
            workspaces=MappingProxyType({})
        )

        self._snapshot_count = 0

        self._lock = RLock()

    def register(self, workspace) -> None:
        """
        Register a binding workspace.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError:
                If the workspace is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
                has an empty or blank workspace ID, or its workspace
                ID is already registered
        """

        self._validate_workspace(workspace)

        with self._lock:
            if workspace.workspace_id in self._registry.workspaces:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError(
                    f"Cannot register a binding workspace: workspace ID {workspace.workspace_id!r} is already registered."
                )

            updated = dict(self._registry.workspaces)
            updated[workspace.workspace_id] = workspace

            self._replace_workspaces(updated)

    def replace(self, workspace) -> None:
        """
        Replace an already-registered binding workspace.

        The replaced workspace keeps its original position in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError:
                If the workspace is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
                has an empty or blank workspace ID, or no workspace
                is registered under its workspace ID
        """

        self._validate_workspace(workspace)

        with self._lock:
            if workspace.workspace_id not in self._registry.workspaces:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError(
                    f"Cannot replace a binding workspace: no workspace is registered under workspace ID {workspace.workspace_id!r}."
                )

            updated = dict(self._registry.workspaces)
            updated[workspace.workspace_id] = workspace

            self._replace_workspaces(updated)

    def remove(self, workspace_id) -> None:
        """
        Remove the workspace registered under a workspace ID.

        Unlike a plain deletion, removing a workspace ID that was
        never registered is rejected rather than treated as a no-op.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError:
                If the workspace ID is None or blank, or no workspace
                is registered under it
        """

        self._validate_workspace_id(workspace_id)

        with self._lock:
            if workspace_id not in self._registry.workspaces:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError(
                    f"Cannot remove a binding workspace: no workspace is registered under workspace ID {workspace_id!r}."
                )

            updated = dict(self._registry.workspaces)
            del updated[workspace_id]

            self._replace_workspaces(updated)

    def find(self, workspace_id):
        """
        Find the workspace registered under a workspace ID.

        Returns:
            The matching workspace, or None if no workspace is
            registered under it
        """

        with self._lock:
            return self._registry.workspaces.get(workspace_id)

    def contains(self, workspace_id) -> bool:
        """
        Check whether a workspace is registered under a workspace ID.
        """

        with self._lock:
            return workspace_id in self._registry.workspaces

    def list(self) -> tuple:
        """
        List every registered workspace.

        Returns:
            An immutable tuple of every registered workspace,
            preserving registration order
        """

        with self._lock:
            return tuple(self._registry.workspaces.values())

    def snapshot(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistrySnapshot:
        """
        Take a snapshot of the registry's current state.

        Returns:
            An immutable snapshot carrying the current workspace
            count and the number of times the registry has been
            snapshotted, including this snapshot
        """

        with self._lock:
            self._snapshot_count += 1

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistrySnapshot(
                workspace_count=len(self._registry.workspaces),
                snapshot_count=self._snapshot_count,
            )

    def _replace_workspaces(self, workspaces) -> None:
        self._registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistry(
            workspaces=MappingProxyType(workspaces)
        )

    def _validate_workspace_id(self, workspace_id) -> None:
        if workspace_id is None or not workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError(
                "Cannot operate on a binding workspace with an empty or blank workspace ID."
            )

    def _validate_workspace(self, workspace) -> None:
        if workspace is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError(
                "Cannot register a None binding workspace."
            )

        if not isinstance(
            workspace,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryError(
                "Cannot register a binding workspace: workspace must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace."
            )

        self._validate_workspace_id(workspace.workspace_id)
