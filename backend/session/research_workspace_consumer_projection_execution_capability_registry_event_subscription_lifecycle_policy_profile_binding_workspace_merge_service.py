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

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_merge import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetMerge,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_review_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_conflict_resolution_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_merge_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_merge_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeService:
    """
    Merges multiple approved consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace change sets, all targeting the same workspace, into a
    single, consolidated, deployable change set.

    The service's responsibility is validating mergeability, reusing
    conflict detection to catch conflicting edits, and staging the
    consolidated change set, not change set creation, operation
    staging, review, or conflict resolution themselves. It does NOT
    create change sets outside of the merged one, approve or reject
    reviews, resolve conflicts, apply or discard any change set, or
    mutate a workspace. It operates over a change set service, a
    change set review service, and a conflict service supplied at
    construction time.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Order-preserving: The merged change set's operations appear in
      source change set order, and in each source's original
      operation order
    - Collision-safe: Every merged operation's ID is namespaced with
      its source change set's ID, so operation IDs that happen to
      coincide across sources never collide on the merged change set
    - Conflict-aware: Every source is passed through conflict
      detection before merging; any unresolved conflict, including one
      between two sources being merged, blocks the merge
    - Non-destructive on preview: Previewing a merge never creates the
      consolidated change set or records merge history
    - History-retaining: Every successful merge remains retrievable
      per workspace
    """

    def __init__(self, change_set_service, review_service, conflict_service):
        """
        Args:
            change_set_service: The service used to resolve, create,
                and stage change sets. Any object exposing
                `find(change_set_id)`, `create(workspace_id, name)`,
                and `add_operation(change_set_id, operation)` is
                accepted
            review_service: The service used to resolve a change
                set's aggregate review status. Any object exposing
                `status(change_set_id)` is accepted
            conflict_service: The service used to detect conflicts on
                a change set before merging. Any object exposing
                `detect(change_set_id)` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError:
                If change_set_service, review_service, or
                conflict_service is None
        """

        for dependency, name in (
            (change_set_service, "change set service"),
            (review_service, "change set review service"),
            (conflict_service, "conflict service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                    f"Cannot initialize merge service with a None {name}."
                )

        self._change_set_service = change_set_service
        self._review_service = review_service
        self._conflict_service = conflict_service
        self._merges = {}
        self._merge_order_by_workspace = {}
        self._lock = RLock()

    def merge(
        self,
        change_set_ids,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeResult:
        """
        Merge multiple approved, open change sets targeting the same
        workspace into a single, consolidated change set.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError:
                If change_set_ids is None, empty, contains a blank or
                duplicate ID, references an unknown change set,
                references change sets from more than one workspace,
                or references a change set that is not open or not
                approved

        Returns:
            A result carrying the merged operations on success, or the
            unresolved conflicts that blocked the merge on failure. No
            consolidated change set is created and no merge history is
            recorded when blocked by conflicts
        """

        with self._lock:
            workspace_id, ids, change_sets = self._resolve_and_validate(change_set_ids, strict=True)

            merged_operations, conflicts = self._compute_merge(change_sets)

            if conflicts:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeResult(
                    successful=False,
                    merged_operations=(),
                    conflicts_detected=conflicts,
                )

            merged_change_set = self._change_set_service.create(
                workspace_id,
                f"Merge of {', '.join(ids)}",
            )

            for operation in merged_operations:
                self._change_set_service.add_operation(merged_change_set.change_set_id, operation)

            merge_record = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetMerge(
                merge_id=str(uuid4()),
                workspace_id=workspace_id,
                source_change_set_ids=ids,
                merged_change_set_id=merged_change_set.change_set_id,
                merged_at=datetime.now(timezone.utc),
            )

            self._merges[merge_record.merge_id] = merge_record
            self._merge_order_by_workspace.setdefault(workspace_id, []).append(merge_record.merge_id)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeResult(
                successful=True,
                merged_operations=merged_operations,
                conflicts_detected=(),
            )

    def can_merge(self, change_set_ids) -> bool:
        """
        Check whether merging a set of change sets would currently
        succeed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError:
                If change_set_ids is None, empty, contains a blank ID,
                or references an unknown change set
        """

        with self._lock:
            resolved = self._resolve_and_validate(change_set_ids, strict=False)

            if resolved is None:
                return False

            _, _, change_sets = resolved

            _, conflicts = self._compute_merge(change_sets)

            return not conflicts

    def preview_merge(
        self,
        change_set_ids,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeResult:
        """
        Compute the result a merge of a set of change sets would
        currently produce, without creating the consolidated change
        set or recording merge history.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError:
                If change_set_ids is None, empty, contains a blank or
                duplicate ID, references an unknown change set,
                references change sets from more than one workspace,
                or references a change set that is not open or not
                approved
        """

        with self._lock:
            _, _, change_sets = self._resolve_and_validate(change_set_ids, strict=True)

            merged_operations, conflicts = self._compute_merge(change_sets)

            if conflicts:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeResult(
                    successful=False,
                    merged_operations=(),
                    conflicts_detected=conflicts,
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeResult(
                successful=True,
                merged_operations=merged_operations,
                conflicts_detected=(),
            )

    def merge_history(self, workspace_id: str) -> tuple:
        """
        List every successful merge recorded for a workspace, in the
        order they were performed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError:
                If workspace_id is None or blank
        """

        self._validate_id(workspace_id, "workspace ID")

        with self._lock:
            merge_ids = self._merge_order_by_workspace.get(workspace_id, ())

            return tuple(self._merges[merge_id] for merge_id in merge_ids)

    def find(self, merge_id: str):
        """
        Find the merge record registered under a merge ID.

        Returns:
            The matching merge record, or None if no merge is
            registered under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError:
                If merge_id is None or blank
        """

        self._validate_id(merge_id, "merge ID")

        with self._lock:
            return self._merges.get(merge_id)

    def _compute_merge(self, change_sets: list) -> tuple:
        conflicts = []
        seen_conflict_ids = set()

        for change_set in change_sets:
            for conflict in self._conflict_service.detect(change_set.change_set_id):
                if (
                    conflict.resolution_status
                    == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus.UNRESOLVED
                    and conflict.conflict_id not in seen_conflict_ids
                ):
                    seen_conflict_ids.add(conflict.conflict_id)
                    conflicts.append(conflict)

        if conflicts:
            return (), tuple(conflicts)

        merged_operations = tuple(
            replace(operation, operation_id=f"{change_set.change_set_id}:{operation.operation_id}")
            for change_set in change_sets
            for operation in change_set.operations
        )

        return merged_operations, ()

    def _resolve_and_validate(self, change_set_ids, strict: bool):
        ids = self._validate_id_list(change_set_ids)

        if len(set(ids)) != len(ids):
            if strict:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                    "Cannot merge: change set IDs must not contain duplicates."
                )

            return None

        change_sets = []

        for change_set_id in ids:
            change_set = self._change_set_service.find(change_set_id)

            if change_set is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                    f"Cannot merge: no change set is registered under change set ID {change_set_id!r}."
                )

            change_sets.append(change_set)

        workspace_ids = {change_set.workspace_id for change_set in change_sets}

        if len(workspace_ids) != 1:
            if strict:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                    "Cannot merge change sets that target different workspaces."
                )

            return None

        workspace_id = next(iter(workspace_ids))

        for change_set in change_sets:
            if change_set.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
                if strict:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                        f"Cannot merge change set ID {change_set.change_set_id!r}: it is {change_set.status.value}, not open."
                    )

                return None

            if (
                self._review_service.status(change_set.change_set_id)
                != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewStatus.APPROVED
            ):
                if strict:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                        f"Cannot merge change set ID {change_set.change_set_id!r}: it is not approved."
                    )

                return None

        return workspace_id, ids, change_sets

    def _validate_id_list(self, change_set_ids) -> tuple:
        if change_set_ids is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                "Cannot merge with a None list of change set IDs."
            )

        ids = tuple(change_set_ids)

        if not ids:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                "Cannot merge an empty list of change set IDs."
            )

        for change_set_id in ids:
            self._validate_id(change_set_id, "change set ID")

        return ids

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                f"Cannot operate on a merge with an empty or blank {label}."
            )
