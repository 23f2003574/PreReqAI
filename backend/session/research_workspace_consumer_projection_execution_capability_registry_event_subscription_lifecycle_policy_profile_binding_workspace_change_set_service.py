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

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_operation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_preview import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetPreview,
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


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService:
    """
    Stages, previews, applies, and discards batches of edits
    (change sets) to consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspaces, so multiple edits can be reviewed together and
    committed atomically instead of modifying a workspace directly.

    The service's responsibility is change set lifecycle management,
    not workspace creation, binding, template, preset, or group
    creation, profile validation, or policy evaluation. It does NOT
    create workspaces, create bindings, binding templates, binding
    presets, or binding groups, validate profiles, evaluate policies,
    persist change sets externally, log, or publish events. It
    operates over a workspace service supplied at construction time,
    updating the workspace only when a change set is applied.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two operations staged on the same change set
      may share an operation ID
    - Order-preserving: A change set's operations are applied in the
      order they were staged
    - Atomic: Applying a change set either updates the workspace with
      every staged operation reflected, or leaves the workspace
      completely untouched if any operation cannot be applied
    - Non-destructive on preview: Computing a preview never mutates
      the change set or the workspace it targets
    - Terminal on apply/discard: An applied or discarded change set
      can no longer be mutated, applied, or discarded again
    """

    def __init__(self, workspace_service):
        """
        Args:
            workspace_service: The service used to resolve and update
                the workspace a change set targets. Any object
                exposing `find(workspace_id)`, returning an object
                with `binding_ids`, `template_ids`, `preset_ids`, and
                `group_ids` collections, and `update(workspace)` is
                accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError:
                If workspace_service is None
        """

        if workspace_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot initialize change set service with a None workspace service."
            )

        self._workspace_service = workspace_service
        self._change_sets = {}
        self._change_set_order = []
        self._lock = RLock()

    def create(
        self,
        workspace_id: str,
        name: str,
        description: str | None = None,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet:
        """
        Create an empty, open change set targeting a workspace.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError:
                If workspace_id or name is None or blank, or no
                workspace is registered under workspace_id
        """

        self._validate_id(workspace_id, "workspace ID")

        if name is None or not name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot create a change set with an empty or blank name."
            )

        with self._lock:
            self._resolve_workspace(workspace_id)

            change_set_id = str(uuid4())

            change_set = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet(
                change_set_id=change_set_id,
                workspace_id=workspace_id,
                name=name,
                description=description,
                operations=(),
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN,
                created_at=datetime.now(timezone.utc),
            )

            self._change_sets[change_set_id] = change_set
            self._change_set_order.append(change_set_id)

            return change_set

    def add_operation(
        self,
        change_set_id: str,
        operation: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet:
        """
        Stage an operation onto an open change set.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError:
                If change_set_id is None or blank, operation is None
                or not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation,
                no change set is registered under change_set_id, the
                change set is not open, or its operation ID is
                already staged on the change set
        """

        self._validate_id(change_set_id, "change set ID")
        self._validate_operation(operation)

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)

            self._require_open(change_set, "add an operation to")

            if any(existing.operation_id == operation.operation_id for existing in change_set.operations):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                    f"Cannot add operation: operation ID {operation.operation_id!r} is already staged on "
                    f"change set ID {change_set_id!r}."
                )

            updated = replace(change_set, operations=change_set.operations + (operation,))
            self._change_sets[change_set_id] = updated

            return updated

    def remove_operation(
        self,
        change_set_id: str,
        operation_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet:
        """
        Remove a staged operation from an open change set.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError:
                If change_set_id or operation_id is None or blank, no
                change set is registered under change_set_id, the
                change set is not open, or no operation is staged
                under operation_id
        """

        self._validate_id(change_set_id, "change set ID")
        self._validate_id(operation_id, "operation ID")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)

            self._require_open(change_set, "remove an operation from")

            if not any(existing.operation_id == operation_id for existing in change_set.operations):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                    f"Cannot remove operation: no operation is staged under operation ID {operation_id!r} on "
                    f"change set ID {change_set_id!r}."
                )

            updated = replace(
                change_set,
                operations=tuple(
                    existing for existing in change_set.operations if existing.operation_id != operation_id
                ),
            )
            self._change_sets[change_set_id] = updated

            return updated

    def preview(
        self,
        change_set_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetPreview:
        """
        Compute the workspace state that would result from applying a
        change set's staged operations, without persisting it.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError:
                If change_set_id is None or blank, no change set is
                registered under it, its workspace is no longer
                registered, or one of its staged operations cannot be
                applied to the workspace's current state
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)
            workspace = self._resolve_workspace(change_set.workspace_id)

            resulting_state = self._compute_resulting_state(workspace, change_set.operations)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetPreview(
                change_set_id=change_set.change_set_id,
                workspace_id=change_set.workspace_id,
                binding_ids=resulting_state["binding"],
                template_ids=resulting_state["template"],
                preset_ids=resulting_state["preset"],
                group_ids=resulting_state["group"],
            )

    def apply(
        self,
        change_set_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet:
        """
        Apply every staged operation on an open change set to its
        workspace atomically, then mark the change set applied.

        Every operation is validated against the workspace's current
        state before the workspace is updated, so a single invalid
        operation leaves the workspace completely untouched.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError:
                If change_set_id is None or blank, no change set is
                registered under it, the change set is not open, it
                has no staged operations, its workspace is no longer
                registered, or one of its staged operations cannot be
                applied to the workspace's current state
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)

            self._require_open(change_set, "apply")

            if not change_set.operations:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                    f"Cannot apply change set ID {change_set_id!r}: it has no staged operations."
                )

            workspace = self._resolve_workspace(change_set.workspace_id)

            resulting_state = self._compute_resulting_state(workspace, change_set.operations)

            updated_workspace = replace(
                workspace,
                binding_ids=resulting_state["binding"],
                template_ids=resulting_state["template"],
                preset_ids=resulting_state["preset"],
                group_ids=resulting_state["group"],
            )

            self._workspace_service.update(updated_workspace)

            applied = replace(
                change_set,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.APPLIED,
            )
            self._change_sets[change_set_id] = applied

            return applied

    def discard(
        self,
        change_set_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet:
        """
        Discard an open change set without affecting its workspace.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError:
                If change_set_id is None or blank, no change set is
                registered under it, or the change set is not open
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)

            self._require_open(change_set, "discard")

            discarded = replace(
                change_set,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.DISCARDED,
            )
            self._change_sets[change_set_id] = discarded

            return discarded

    def find(self, change_set_id: str):
        """
        Find the change set registered under a change set ID.

        Returns:
            The matching change set, or None if no change set is
            registered under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError:
                If change_set_id is None or blank
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            return self._change_sets.get(change_set_id)

    def list(self) -> tuple:
        """
        List every registered change set, in creation order.
        """

        with self._lock:
            return tuple(self._change_sets[change_set_id] for change_set_id in self._change_set_order)

    def _compute_resulting_state(self, workspace, operations: tuple) -> dict:
        state = {
            resource_type: list(getattr(workspace, attribute))
            for resource_type, attribute in _RESOURCE_ATTRIBUTES.items()
        }

        for operation in operations:
            member_ids = state[operation.resource_type]

            if operation.operation_type == "add":
                if operation.resource_id in member_ids:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                        f"Cannot apply operation ID {operation.operation_id!r}: {operation.resource_type} ID "
                        f"{operation.resource_id!r} is already a member of workspace ID {workspace.workspace_id!r}."
                    )

                member_ids.append(operation.resource_id)
            else:
                if operation.resource_id not in member_ids:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                        f"Cannot apply operation ID {operation.operation_id!r}: {operation.resource_type} ID "
                        f"{operation.resource_id!r} is not a member of workspace ID {workspace.workspace_id!r}."
                    )

                member_ids.remove(operation.resource_id)

        return {resource_type: tuple(member_ids) for resource_type, member_ids in state.items()}

    def _resolve_change_set(
        self,
        change_set_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet:
        change_set = self._change_sets.get(change_set_id)

        if change_set is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                f"Cannot operate on a change set: no change set is registered under change set ID {change_set_id!r}."
            )

        return change_set

    def _resolve_workspace(self, workspace_id: str):
        workspace = self._workspace_service.find(workspace_id)

        if workspace is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                f"Cannot operate on a change set: no workspace is registered under workspace ID {workspace_id!r}."
            )

        return workspace

    def _require_open(
        self,
        change_set: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet,
        action: str,
    ) -> None:
        if change_set.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                f"Cannot {action} change set ID {change_set.change_set_id!r}: it is {change_set.status.value}, not open."
            )

    def _validate_operation(self, operation) -> None:
        if operation is None or not isinstance(
            operation,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot add operation: operation must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                f"Cannot operate on a change set with an empty or blank {label}."
            )
