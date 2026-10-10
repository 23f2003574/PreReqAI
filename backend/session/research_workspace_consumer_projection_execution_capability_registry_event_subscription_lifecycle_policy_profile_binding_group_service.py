from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_collection import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCollection,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupService:
    """
    Groups consumer projection execution capability registry event
    subscription lifecycle policy profile bindings into reusable
    logical units for bulk management and deployment.

    The service's responsibility is group creation, update, removal,
    lookup, listing, and membership management, not binding creation,
    profile validation, policy evaluation, persistence, logging, or
    event publication. It does NOT create bindings, validate
    profiles, evaluate policies, persist groups, log, or publish
    events. Every mutation produces a new, immutable group record; no
    group record is ever mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two registered groups may share a group ID,
      and no group may contain the same member binding twice
    - Unrestricted fan-out: A binding may belong to any number of
      groups
    - Order-preserving: Groups are listed in the order they were
      first created, and group membership is listed in the order
      members were added
    """

    def __init__(self, binding_service):
        """
        Args:
            binding_service: The binding service used to verify a
                binding exists before it is added to a group. Any
                object exposing `contains(binding_id)` is accepted
        """

        if binding_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                "Cannot initialize binding group service with a None binding service."
            )

        self._binding_service = binding_service
        self._groups = {}
        self._group_order = []
        self._lock = RLock()

    def create(
        self,
        group: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup:
        """
        Create a binding group.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError:
                If the group is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
                its group ID is already registered, or any of its
                member bindings is unknown
        """

        self._validate_group(group)

        with self._lock:
            if group.group_id in self._groups:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                    f"Cannot create a binding group: group ID {group.group_id!r} is already registered."
                )

            self._validate_members(group.binding_ids)

            self._groups[group.group_id] = group
            self._group_order.append(group.group_id)

            return group

    def update(
        self,
        group: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup:
        """
        Update an already-registered binding group.

        The updated group keeps its original position in registration
        order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError:
                If the group is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
                no group is registered under its group ID, or any of
                its member bindings is unknown
        """

        self._validate_group(group)

        with self._lock:
            if group.group_id not in self._groups:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                    f"Cannot update a binding group: no group is registered under group ID {group.group_id!r}."
                )

            self._validate_members(group.binding_ids)

            self._groups[group.group_id] = group

            return group

    def remove(
        self,
        group_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup:
        """
        Remove the group registered under a group ID.

        Unlike a plain deletion, removing a group ID that was never
        registered is rejected rather than treated as a no-op.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError:
                If the group ID is None or blank, or no group is
                registered under it
        """

        self._validate_group_id(group_id)

        with self._lock:
            if group_id not in self._groups:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                    f"Cannot remove a binding group: no group is registered under group ID {group_id!r}."
                )

            group = self._groups.pop(group_id)
            self._group_order.remove(group_id)

            return group

    def find(self, group_id: str):
        """
        Find the group registered under a group ID.

        Returns:
            The matching group, or None if no group is registered
            under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError:
                If the group ID is None or blank
        """

        self._validate_group_id(group_id)

        with self._lock:
            return self._groups.get(group_id)

    def list(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCollection:
        """
        List every registered group, in deterministic order.
        """

        with self._lock:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupCollection(
                groups=tuple(self._groups[group_id] for group_id in self._group_order),
            )

    def add_binding(
        self,
        group_id: str,
        binding_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup:
        """
        Add a binding to a group's membership.

        The new member is appended after every existing member.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError:
                If the group ID or binding ID is None or blank, no
                group is registered under the group ID, the binding
                is unknown, or the binding is already a member of the
                group
        """

        self._validate_group_id(group_id)
        self._validate_binding_id(binding_id)

        with self._lock:
            group = self._groups.get(group_id)

            if group is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                    f"Cannot add a binding to a group: no group is registered under group ID {group_id!r}."
                )

            if not self._binding_service.contains(binding_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                    f"Cannot add a binding to a group: no binding is registered under binding ID {binding_id!r}."
                )

            if binding_id in group.binding_ids:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                    f"Cannot add a binding to a group: binding ID {binding_id!r} is already a member of group ID {group_id!r}."
                )

            updated = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
                group_id=group.group_id,
                group_name=group.group_name,
                binding_ids=group.binding_ids + (binding_id,),
            )

            self._groups[group_id] = updated

            return updated

    def remove_binding(
        self,
        group_id: str,
        binding_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup:
        """
        Remove a binding from a group's membership.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError:
                If the group ID or binding ID is None or blank, no
                group is registered under the group ID, or the
                binding is not a member of the group
        """

        self._validate_group_id(group_id)
        self._validate_binding_id(binding_id)

        with self._lock:
            group = self._groups.get(group_id)

            if group is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                    f"Cannot remove a binding from a group: no group is registered under group ID {group_id!r}."
                )

            if binding_id not in group.binding_ids:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                    f"Cannot remove a binding from a group: binding ID {binding_id!r} is not a member of group ID {group_id!r}."
                )

            updated = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
                group_id=group.group_id,
                group_name=group.group_name,
                binding_ids=tuple(
                    existing_binding_id
                    for existing_binding_id in group.binding_ids
                    if existing_binding_id != binding_id
                ),
            )

            self._groups[group_id] = updated

            return updated

    def _validate_members(self, binding_ids) -> None:
        for binding_id in binding_ids:
            if not self._binding_service.contains(binding_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                    f"Cannot save a binding group: no binding is registered under binding ID {binding_id!r}."
                )

    def _validate_group_id(self, group_id) -> None:
        if group_id is None or not group_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                "Cannot operate on a binding group with an empty or blank group ID."
            )

    def _validate_binding_id(self, binding_id) -> None:
        if binding_id is None or not binding_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                "Cannot operate on a binding group with an empty or blank binding ID."
            )

    def _validate_group(self, group) -> None:
        if group is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                "Cannot save a None binding group."
            )

        if not isinstance(
            group,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupError(
                "Cannot save a binding group: group must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup."
            )

        self._validate_group_id(group.group_id)
