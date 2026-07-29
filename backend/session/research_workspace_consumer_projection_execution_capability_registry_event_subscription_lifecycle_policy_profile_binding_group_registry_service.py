from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_registry_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistrySnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService:
    """
    Maintains a centralised registry of consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding groups, addressed by group identifier, for fast lookup,
    replacement, and snapshot generation.

    The service's responsibility is group registration, replacement,
    removal, lookup, containment checking, listing, and snapshot
    generation, not group creation, membership management, profile
    validation, policy evaluation, persistence, logging, or event
    publication. It does NOT create groups, manage group membership,
    validate profiles, evaluate policies, persist the registry, log,
    or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two registered groups may share a group ID
    - Order-preserving: Groups are listed in the order they were
      first registered
    - Immutable registry: The underlying registry value object is
      replaced atomically on every mutation rather than mutated in
      place
    """

    def __init__(self):
        self._registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistry(
            groups=MappingProxyType({})
        )

        self._lock = RLock()

    def register(self, group) -> None:
        """
        Register a binding group.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError:
                If the group is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
                has an empty or blank group ID, or its group ID is
                already registered
        """

        self._validate_group(group)

        with self._lock:
            if group.group_id in self._registry.groups:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError(
                    f"Cannot register a binding group: group ID {group.group_id!r} is already registered."
                )

            updated = dict(self._registry.groups)
            updated[group.group_id] = group

            self._replace_groups(updated)

    def replace(self, group) -> None:
        """
        Replace an already-registered binding group.

        The replaced group keeps its original position in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError:
                If the group is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
                has an empty or blank group ID, or no group is
                registered under its group ID
        """

        self._validate_group(group)

        with self._lock:
            if group.group_id not in self._registry.groups:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError(
                    f"Cannot replace a binding group: no group is registered under group ID {group.group_id!r}."
                )

            updated = dict(self._registry.groups)
            updated[group.group_id] = group

            self._replace_groups(updated)

    def remove(self, group_id) -> None:
        """
        Remove the group registered under a group ID.

        Unlike a plain deletion, removing a group ID that was never
        registered is rejected rather than treated as a no-op.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError:
                If the group ID is None or blank, or no group is
                registered under it
        """

        self._validate_group_id(group_id)

        with self._lock:
            if group_id not in self._registry.groups:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError(
                    f"Cannot remove a binding group: no group is registered under group ID {group_id!r}."
                )

            updated = dict(self._registry.groups)
            del updated[group_id]

            self._replace_groups(updated)

    def find(self, group_id):
        """
        Find the group registered under a group ID.

        Returns:
            The matching group, or None if no group is registered
            under it
        """

        with self._lock:
            return self._registry.groups.get(group_id)

    def contains(self, group_id) -> bool:
        """
        Check whether a group is registered under a group ID.
        """

        with self._lock:
            return group_id in self._registry.groups

    def list(self) -> tuple:
        """
        List every registered group.

        Returns:
            An immutable tuple of every registered group, preserving
            registration order
        """

        with self._lock:
            return tuple(self._registry.groups.values())

    def snapshot(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistrySnapshot:
        """
        Take a snapshot of the registry's current state.

        Returns:
            An immutable snapshot carrying the current group count and
            the number of distinct binding identifiers referenced
            among the registered groups' members
        """

        with self._lock:
            groups = self._registry.groups

            binding_ids = set()
            for group in groups.values():
                binding_ids.update(group.binding_ids)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistrySnapshot(
                group_count=len(groups),
                binding_count=len(binding_ids),
            )

    def _replace_groups(self, groups) -> None:
        self._registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistry(
            groups=MappingProxyType(groups)
        )

    def _validate_group_id(self, group_id) -> None:
        if group_id is None or not group_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError(
                "Cannot operate on a binding group with an empty or blank group ID."
            )

    def _validate_group(self, group) -> None:
        if group is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError(
                "Cannot register a None binding group."
            )

        if not isinstance(
            group,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryError(
                "Cannot register a binding group: group must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup."
            )

        self._validate_group_id(group.group_id)
