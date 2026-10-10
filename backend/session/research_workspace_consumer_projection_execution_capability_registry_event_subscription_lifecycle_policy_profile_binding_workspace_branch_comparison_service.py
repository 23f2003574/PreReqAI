from threading import (
    RLock,
)

from types import MappingProxyType

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_comparison import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparison,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_comparison_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_difference import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchDifference,
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


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonService:
    """
    Computes resource-by-resource comparisons between two consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace branches, so
    differences can be inspected before synchronization or merge.

    The service's responsibility is comparison, summarization,
    conflict detection, and export, not branch creation, checkout,
    renaming, or closing, or change set creation, review, merging, or
    rebasing themselves. It does NOT create, checkout, rename, or
    close a branch, or create, stage, review, merge, or rebase change
    sets, or mutate a workspace. A branch's prospective state is
    computed the same way a merge preview would: its workspace's
    current member resources, adjusted by every operation staged on
    its workspace's open change sets, so this service integrates with
    the merge preview workflow without depending on the merge service
    directly.

    A resource is classified relative to source_branch:
    - "addition": source has, or will have, the resource; target does
      not
    - "deletion": target has the resource; source does not, or will
      not
    - "update": both branches currently share the resource, but at
      least one has a pending change queued against it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Deterministic: The same pair of branches, in the same state,
      always produces differences in the same order — resource type,
      then resource ID
    - Non-mutating: Comparing, summarizing, checking for conflicts in,
      and exporting a comparison never changes a branch, a workspace,
      or a change set
    - History-retaining: Every comparison computed remains retrievable
      by its comparison ID
    """

    def __init__(self, branch_service, workspace_service, change_set_service):
        """
        Args:
            branch_service: The service used to resolve a branch's
                workspace ID. Any object exposing `find(branch_id)` is
                accepted
            workspace_service: The service used to resolve a
                workspace's current member resources. Any object
                exposing `find(workspace_id)`, returning an object
                with `binding_ids`, `template_ids`, `preset_ids`, and
                `group_ids` collections, is accepted
            change_set_service: The service used to enumerate the
                change sets staged against a branch's workspace. Any
                object exposing `list()` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError:
                If branch_service, workspace_service, or
                change_set_service is None
        """

        for dependency, name in (
            (branch_service, "branch service"),
            (workspace_service, "workspace service"),
            (change_set_service, "change set service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                    f"Cannot initialize branch comparison service with a None {name}."
                )

        self._branch_service = branch_service
        self._workspace_service = workspace_service
        self._change_set_service = change_set_service
        self._comparisons = {}
        self._lock = RLock()

    def compare(
        self,
        source_branch_id: str,
        target_branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparison:
        """
        Compare two branches resource-by-resource.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError:
                If source_branch_id or target_branch_id is None or
                blank, they are equal, no branch is registered under
                either, or either branch's workspace is no longer
                registered
        """

        self._validate_id(source_branch_id, "source branch ID")
        self._validate_id(target_branch_id, "target branch ID")

        if source_branch_id == target_branch_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                "Cannot compare a branch against itself: source_branch_id and target_branch_id must be different."
            )

        with self._lock:
            source_branch = self._resolve_branch(source_branch_id)
            target_branch = self._resolve_branch(target_branch_id)

            source_workspace = self._resolve_workspace(source_branch.workspace_id)
            target_workspace = self._resolve_workspace(target_branch.workspace_id)

            differences = self._compute_differences(
                source_workspace,
                source_branch.workspace_id,
                target_workspace,
                target_branch.workspace_id,
            )

            comparison = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparison(
                comparison_id=str(uuid4()),
                source_branch=source_branch,
                target_branch=target_branch,
                differences=differences,
            )

            self._comparisons[comparison.comparison_id] = comparison

            return comparison

    def summary(self, comparison_id: str) -> MappingProxyType:
        """
        Summarize a comparison's differences by change type.

        Returns:
            An immutable mapping of "addition", "update", "deletion",
            and "total" to their counts

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError:
                If comparison_id is None or blank, or no comparison is
                registered under it
        """

        self._validate_id(comparison_id, "comparison ID")

        with self._lock:
            comparison = self._resolve_comparison(comparison_id)

        counts = {"addition": 0, "update": 0, "deletion": 0}

        for difference in comparison.differences:
            counts[difference.change_type] += 1

        counts["total"] = len(comparison.differences)

        return MappingProxyType(counts)

    def has_conflicts(self, comparison_id: str) -> bool:
        """
        Check whether a comparison found any resource that both
        branches currently share but are changing differently.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError:
                If comparison_id is None or blank, or no comparison is
                registered under it
        """

        self._validate_id(comparison_id, "comparison ID")

        with self._lock:
            comparison = self._resolve_comparison(comparison_id)

        return any(difference.change_type == "update" for difference in comparison.differences)

    def export(self, comparison_id: str) -> MappingProxyType:
        """
        Export a comparison as an immutable, serialization-friendly
        mapping of primitive values.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError:
                If comparison_id is None or blank, or no comparison is
                registered under it
        """

        self._validate_id(comparison_id, "comparison ID")

        with self._lock:
            comparison = self._resolve_comparison(comparison_id)

        return MappingProxyType(
            {
                "comparison_id": comparison.comparison_id,
                "source_branch_id": comparison.source_branch.branch_id,
                "target_branch_id": comparison.target_branch.branch_id,
                "differences": tuple(
                    MappingProxyType(
                        {
                            "resource_type": difference.resource_type,
                            "resource_id": difference.resource_id,
                            "change_type": difference.change_type,
                        }
                    )
                    for difference in comparison.differences
                ),
            }
        )

    def find(self, comparison_id: str):
        """
        Find the comparison registered under a comparison ID.

        Returns:
            The matching comparison, or None if no comparison is
            registered under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError:
                If comparison_id is None or blank
        """

        self._validate_id(comparison_id, "comparison ID")

        with self._lock:
            return self._comparisons.get(comparison_id)

    def _compute_differences(
        self,
        source_workspace,
        source_workspace_id: str,
        target_workspace,
        target_workspace_id: str,
    ) -> tuple:
        differences = []

        for resource_type, attribute in _RESOURCE_ATTRIBUTES.items():
            current_source = set(getattr(source_workspace, attribute))
            current_target = set(getattr(target_workspace, attribute))

            pending_source = self._pending_operations(source_workspace_id, resource_type)
            pending_target = self._pending_operations(target_workspace_id, resource_type)

            all_ids = current_source | current_target | set(pending_source) | set(pending_target)

            for resource_id in sorted(all_ids):
                source_present = self._prospective(resource_id, current_source, pending_source)
                target_present = self._prospective(resource_id, current_target, pending_target)

                if source_present and not target_present:
                    change_type = "addition"
                elif target_present and not source_present:
                    change_type = "deletion"
                elif source_present and target_present and (
                    resource_id in pending_source or resource_id in pending_target
                ):
                    change_type = "update"
                else:
                    continue

                differences.append(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchDifference(
                        resource_type=resource_type,
                        resource_id=resource_id,
                        change_type=change_type,
                    )
                )

        return tuple(differences)

    def _pending_operations(self, workspace_id: str, resource_type: str) -> dict:
        pending = {}

        for change_set in self._change_set_service.list():
            if change_set.workspace_id != workspace_id:
                continue

            if change_set.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
                continue

            for operation in change_set.operations:
                if operation.resource_type == resource_type:
                    pending[operation.resource_id] = operation.operation_type

        return pending

    def _prospective(self, resource_id: str, current_ids: set, pending_ops: dict) -> bool:
        operation_type = pending_ops.get(resource_id)

        if operation_type == "add":
            return True

        if operation_type == "remove":
            return False

        return resource_id in current_ids

    def _resolve_branch(self, branch_id: str):
        branch = self._branch_service.find(branch_id)

        if branch is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                f"Cannot compare branches: no branch is registered under branch ID {branch_id!r}."
            )

        return branch

    def _resolve_workspace(self, workspace_id: str):
        workspace = self._workspace_service.find(workspace_id)

        if workspace is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                f"Cannot compare branches: no workspace is registered under workspace ID {workspace_id!r}."
            )

        return workspace

    def _resolve_comparison(
        self,
        comparison_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparison:
        comparison = self._comparisons.get(comparison_id)

        if comparison is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                f"Cannot operate on a branch comparison: no comparison is registered under comparison ID "
                f"{comparison_id!r}."
            )

        return comparison

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchComparisonError(
                f"Cannot operate on a branch comparison with an empty or blank {label}."
            )
