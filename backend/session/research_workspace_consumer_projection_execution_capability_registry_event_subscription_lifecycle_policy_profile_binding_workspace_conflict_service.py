from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_conflict import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeConflict,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_conflict_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_conflict_resolution import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolution,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_conflict_resolution_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus,
)

_RESOURCE_ATTRIBUTES = {
    "binding": "binding_ids",
    "template": "template_ids",
    "preset": "preset_ids",
    "group": "group_ids",
}

_AUTO_RESOLVABLE_CONFLICT_TYPES = ("stale_state",)

_VALID_STRATEGIES = ("manual", "auto")


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictService:
    """
    Detects and resolves resource-level conflicts on consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace change sets, so
    conflicting edits are caught and resolved before an approved
    change set is applied to its workspace.

    The service's responsibility is conflict detection and
    resolution, not change set creation, operation staging, review,
    previewing, applying, or discarding, or workspace mutation. It
    does NOT create change sets, stage or remove operations, review,
    preview, apply, or discard a change set, or mutate a workspace. It
    operates over a change set service and a workspace service
    supplied at construction time, using both only to read current
    state.

    Two kinds of conflict are detected:
    - "stale_state": a staged operation no longer matches the
      workspace's current state (adding a resource already present,
      or removing a resource no longer present)
    - "concurrent_edit": another open change set on the same
      workspace also stages an operation against the same resource

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Idempotent on detect: Re-running detection for a change set
      never duplicates a conflict already recorded for the same
      resource and conflict type, whether or not it has since been
      resolved
    - History-retaining: Every conflict ever detected for a change
      set remains retrievable, including resolved ones
    - Resolution-typed: Automatic resolution is only permitted for
      conflict types it can safely resolve without human judgment;
      all other conflict types require manual resolution
    - Terminal on resolve: A resolved conflict can no longer be
      resolved again
    """

    def __init__(self, change_set_service, workspace_service):
        """
        Args:
            change_set_service: The service used to resolve a change
                set's workspace ID, status, and staged operations, and
                to list every registered change set. Any object
                exposing `find(change_set_id)` and `list()` is
                accepted
            workspace_service: The service used to resolve a
                workspace's current member resources. Any object
                exposing `find(workspace_id)`, returning an object
                with `binding_ids`, `template_ids`, `preset_ids`, and
                `group_ids` collections, is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError:
                If change_set_service or workspace_service is None
        """

        if change_set_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot initialize conflict service with a None change set service."
            )

        if workspace_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot initialize conflict service with a None workspace service."
            )

        self._change_set_service = change_set_service
        self._workspace_service = workspace_service
        self._conflicts = {}
        self._conflict_order_by_change_set = {}
        self._resolutions = {}
        self._lock = RLock()

    def detect(self, change_set_id: str) -> tuple:
        """
        Detect resource-level conflicts on a change set's staged
        operations, against both the workspace's current state and
        every other open change set on the same workspace.

        Calling this repeatedly never duplicates a conflict already
        recorded for the same resource and conflict type; the
        previously recorded conflict, resolved or not, is retained
        instead.

        Returns:
            Every conflict ever recorded for the change set, including
            ones resolved before this call, in detection order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError:
                If change_set_id is None or blank, no change set is
                registered under it, or its workspace is no longer
                registered
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)
            workspace = self._resolve_workspace(change_set.workspace_id)

            for resource_id, conflict_type in self._find_stale_state_conflicts(change_set, workspace):
                self._record_conflict(change_set_id, resource_id, conflict_type)

            for resource_id, conflict_type in self._find_concurrent_edit_conflicts(change_set):
                self._record_conflict(change_set_id, resource_id, conflict_type)

            return self.history(change_set_id)

    def resolve(
        self,
        conflict_id: str,
        strategy: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolution:
        """
        Resolve a conflict using a resolution strategy.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError:
                If conflict_id or strategy is None or blank, no
                conflict is registered under conflict_id, the conflict
                is already resolved, strategy is not "manual" or
                "auto", or strategy is "auto" and the conflict's type
                cannot be resolved automatically
        """

        self._validate_id(conflict_id, "conflict ID")

        if strategy is None or not strategy.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                "Cannot resolve a conflict with an empty or blank strategy."
            )

        if strategy not in _VALID_STRATEGIES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                f"Invalid conflict resolution strategy {strategy!r}. Must be one of {_VALID_STRATEGIES!r}."
            )

        with self._lock:
            conflict = self._resolve_conflict(conflict_id)

            if (
                conflict.resolution_status
                == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus.RESOLVED
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                    f"Cannot resolve conflict ID {conflict_id!r}: it is already resolved."
                )

            if strategy == "auto" and conflict.conflict_type not in _AUTO_RESOLVABLE_CONFLICT_TYPES:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                    f"Cannot automatically resolve conflict ID {conflict_id!r}: conflicts of type "
                    f"{conflict.conflict_type!r} require manual resolution."
                )

            resolved_conflict = replace(
                conflict,
                resolution_status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus.RESOLVED,
            )
            self._conflicts[conflict_id] = resolved_conflict

            resolution = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolution(
                conflict_id=conflict_id,
                strategy=strategy,
                resolved_at=datetime.now(timezone.utc),
            )
            self._resolutions[conflict_id] = resolution

            return resolution

    def remaining(self, change_set_id: str) -> tuple:
        """
        List every unresolved conflict currently recorded for a
        change set, without re-running detection.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError:
                If change_set_id is None or blank, or no change set is
                registered under it
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            self._resolve_change_set(change_set_id)

            return tuple(
                conflict
                for conflict in self.history(change_set_id)
                if conflict.resolution_status
                == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus.UNRESOLVED
            )

    def can_apply(self, change_set_id: str) -> bool:
        """
        Check whether a change set is open and has no unresolved
        conflicts recorded against it.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError:
                If change_set_id is None or blank, or no change set is
                registered under it
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)

            if change_set.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
                return False

            return len(self.remaining(change_set_id)) == 0

    def history(self, change_set_id: str) -> tuple:
        """
        List every conflict ever recorded for a change set, including
        resolved ones, in detection order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError:
                If change_set_id is None or blank
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            conflict_ids = self._conflict_order_by_change_set.get(change_set_id, ())

            return tuple(self._conflicts[conflict_id] for conflict_id in conflict_ids)

    def find(self, conflict_id: str):
        """
        Find the conflict registered under a conflict ID.

        Returns:
            The matching conflict, or None if no conflict is
            registered under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError:
                If conflict_id is None or blank
        """

        self._validate_id(conflict_id, "conflict ID")

        with self._lock:
            return self._conflicts.get(conflict_id)

    def _find_stale_state_conflicts(self, change_set, workspace) -> list:
        found = []

        for operation in change_set.operations:
            member_ids = getattr(workspace, _RESOURCE_ATTRIBUTES[operation.resource_type])

            if operation.operation_type == "add" and operation.resource_id in member_ids:
                found.append((operation.resource_id, "stale_state"))
            elif operation.operation_type == "remove" and operation.resource_id not in member_ids:
                found.append((operation.resource_id, "stale_state"))

        return found

    def _find_concurrent_edit_conflicts(self, change_set) -> list:
        this_resource_ids = {operation.resource_id for operation in change_set.operations}

        found = []
        seen_resource_ids = set()

        for other in self._change_set_service.list():
            if other.change_set_id == change_set.change_set_id:
                continue

            if other.workspace_id != change_set.workspace_id:
                continue

            if other.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
                continue

            for operation in other.operations:
                if operation.resource_id in this_resource_ids and operation.resource_id not in seen_resource_ids:
                    seen_resource_ids.add(operation.resource_id)
                    found.append((operation.resource_id, "concurrent_edit"))

        return found

    def _record_conflict(self, change_set_id: str, resource_id: str, conflict_type: str) -> None:
        existing = self._conflict_order_by_change_set.get(change_set_id, [])

        for conflict_id in existing:
            conflict = self._conflicts[conflict_id]

            if conflict.resource_id == resource_id and conflict.conflict_type == conflict_type:
                return

        conflict = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeConflict(
            conflict_id=str(uuid4()),
            change_set_id=change_set_id,
            resource_id=resource_id,
            conflict_type=conflict_type,
            resolution_status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus.UNRESOLVED,
        )

        self._conflicts[conflict.conflict_id] = conflict
        self._conflict_order_by_change_set.setdefault(change_set_id, []).append(conflict.conflict_id)

    def _resolve_change_set(self, change_set_id: str):
        change_set = self._change_set_service.find(change_set_id)

        if change_set is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                f"Cannot operate on a conflict: no change set is registered under change set ID {change_set_id!r}."
            )

        return change_set

    def _resolve_workspace(self, workspace_id: str):
        workspace = self._workspace_service.find(workspace_id)

        if workspace is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                f"Cannot operate on a conflict: no workspace is registered under workspace ID {workspace_id!r}."
            )

        return workspace

    def _resolve_conflict(
        self,
        conflict_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeConflict:
        conflict = self._conflicts.get(conflict_id)

        if conflict is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                f"Cannot operate on a conflict: no conflict is registered under conflict ID {conflict_id!r}."
            )

        return conflict

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictError(
                f"Cannot operate on a conflict with an empty or blank {label}."
            )
