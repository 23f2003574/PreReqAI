from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_sync import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSync,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_sync_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_sync_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_conflict_resolution_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSynchronizationService:
    """
    Keeps long-lived consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace branches synchronized with their workspace's latest
    published revision, minimizing divergence and merge debt before
    the branch's change sets are merged or rebased.

    The service's responsibility is staleness detection and conflict
    re-checking, not branch creation, checkout, renaming, or closing,
    or change set creation, review, conflict resolution, merging, or
    rebasing themselves. It does NOT create, checkout, rename, or
    close a branch, or create, stage, review, resolve, merge, or
    rebase change sets. It tracks each branch's synchronized revision
    independently of its `head_revision`, which only checkout()
    updates, so synchronizing a branch never changes which branch is
    active for its workspace. It operates over a branch service, a
    change set service, a workspace version service, and a conflict
    service supplied at construction time, reusing conflict detection
    exactly as the merge and rebase workflows do so integration is
    automatic — a branch fails to synchronize whenever any of its
    workspace's open change sets has an unresolved conflict.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Conflict-aware: Every synchronization reuses conflict detection
      against every open change set on the branch's workspace; any
      unresolved conflict blocks it without advancing the branch's
      tracked revision
    - Non-destructive on preview: Previewing a synchronization never
      advances the branch's tracked revision or records sync history
    - History-retaining: Every synchronization attempt, successful or
      not, remains retrievable per branch
    - Read-only-aware: A closed, read-only branch can never be
      synchronized
    """

    def __init__(self, branch_service, change_set_service, workspace_version_service, conflict_service):
        """
        Args:
            branch_service: The service used to resolve a branch's
                workspace ID, base revision, and status. Any object
                exposing `find(branch_id)` is accepted
            change_set_service: The service used to enumerate the
                change sets staged against a branch's workspace. Any
                object exposing `list()` is accepted
            workspace_version_service: The service used to resolve a
                workspace's latest published revision. Any object
                exposing `latest(workspace_id)`, returning an object
                with a `version` attribute and raising
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError
                when no revision has ever been published, is accepted
            conflict_service: The service used to detect conflicts on
                a change set before synchronizing. Any object
                exposing `detect(change_set_id)` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError:
                If any dependency is None
        """

        for dependency, name in (
            (branch_service, "branch service"),
            (change_set_service, "change set service"),
            (workspace_version_service, "workspace version service"),
            (conflict_service, "conflict service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                    f"Cannot initialize branch synchronization service with a None {name}."
                )

        self._branch_service = branch_service
        self._change_set_service = change_set_service
        self._workspace_version_service = workspace_version_service
        self._conflict_service = conflict_service
        self._synced_revision_by_branch = {}
        self._syncs = {}
        self._sync_order_by_branch = {}
        self._lock = RLock()

    def sync(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncResult:
        """
        Synchronize a branch with its workspace's latest published
        revision.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError:
                If branch_id is None or blank, no branch is registered
                under it, the branch is closed, or it is already
                synchronized

        Returns:
            A result carrying a timestamp on success, or the
            unresolved conflicts that blocked synchronization on
            failure. The branch's tracked revision only advances when
            the synchronization succeeds
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            branch = self._resolve_branch(branch_id)
            self._require_not_closed(branch)

            target_revision = self._resolve_target_revision(branch.workspace_id)
            source_revision = self._synced_revision_by_branch.get(branch_id, branch.base_revision)

            if source_revision == target_revision:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                    f"Cannot synchronize branch ID {branch_id!r}: it is already synchronized with revision "
                    f"{target_revision!r}."
                )

            conflicts = self._detect_unresolved_conflicts(branch.workspace_id)

            sync_record = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSync(
                sync_id=str(uuid4()),
                branch_id=branch_id,
                source_revision=source_revision,
                target_revision=target_revision,
                status=(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus.FAILED
                    if conflicts
                    else ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncStatus.SUCCEEDED
                ),
            )

            self._syncs[sync_record.sync_id] = sync_record
            self._sync_order_by_branch.setdefault(branch_id, []).append(sync_record.sync_id)

            if conflicts:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncResult(
                    synchronized=False,
                    conflicts=conflicts,
                    synchronized_at=None,
                )

            self._synced_revision_by_branch[branch_id] = target_revision

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncResult(
                synchronized=True,
                conflicts=(),
                synchronized_at=datetime.now(timezone.utc),
            )

    def can_sync(self, branch_id: str) -> bool:
        """
        Check whether synchronizing a branch would currently succeed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError:
                If branch_id is None or blank, or no branch is
                registered under it
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            branch = self._resolve_branch(branch_id)

            if branch.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.CLOSED:
                return False

            target_revision = self._resolve_target_revision(branch.workspace_id)
            source_revision = self._synced_revision_by_branch.get(branch_id, branch.base_revision)

            if source_revision == target_revision:
                return False

            return not self._detect_unresolved_conflicts(branch.workspace_id)

    def preview_sync(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncResult:
        """
        Compute the result a synchronization of a branch would
        currently produce, without advancing its tracked revision or
        recording sync history.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError:
                If branch_id is None or blank, no branch is registered
                under it, the branch is closed, or it is already
                synchronized
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            branch = self._resolve_branch(branch_id)
            self._require_not_closed(branch)

            target_revision = self._resolve_target_revision(branch.workspace_id)
            source_revision = self._synced_revision_by_branch.get(branch_id, branch.base_revision)

            if source_revision == target_revision:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                    f"Cannot preview a synchronization for branch ID {branch_id!r}: it is already synchronized "
                    f"with revision {target_revision!r}."
                )

            conflicts = self._detect_unresolved_conflicts(branch.workspace_id)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncResult(
                synchronized=not conflicts,
                conflicts=conflicts,
                synchronized_at=None,
            )

    def sync_history(self, branch_id: str) -> tuple:
        """
        List every synchronization attempt recorded for a branch,
        including failed ones, in the order they were attempted.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError:
                If branch_id is None or blank, or no branch is
                registered under it
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            self._resolve_branch(branch_id)

            sync_ids = self._sync_order_by_branch.get(branch_id, ())

            return tuple(self._syncs[sync_id] for sync_id in sync_ids)

    def find(self, sync_id: str):
        """
        Find the sync record registered under a sync ID.

        Returns:
            The matching sync record, or None if no sync is
            registered under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError:
                If sync_id is None or blank
        """

        self._validate_id(sync_id, "sync ID")

        with self._lock:
            return self._syncs.get(sync_id)

    def _detect_unresolved_conflicts(self, workspace_id: str) -> tuple:
        conflicts = []
        seen_conflict_ids = set()

        for change_set in self._change_set_service.list():
            if change_set.workspace_id != workspace_id:
                continue

            if change_set.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
                continue

            for conflict in self._conflict_service.detect(change_set.change_set_id):
                if (
                    conflict.resolution_status
                    == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus.UNRESOLVED
                    and conflict.conflict_id not in seen_conflict_ids
                ):
                    seen_conflict_ids.add(conflict.conflict_id)
                    conflicts.append(conflict)

        return tuple(conflicts)

    def _resolve_target_revision(self, workspace_id: str):
        try:
            return self._workspace_version_service.latest(workspace_id).version
        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError:
            return None

    def _resolve_branch(self, branch_id: str):
        branch = self._branch_service.find(branch_id)

        if branch is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                f"Cannot operate on a branch synchronization: no branch is registered under branch ID {branch_id!r}."
            )

        return branch

    def _require_not_closed(self, branch) -> None:
        if branch.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.CLOSED:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                f"Cannot synchronize branch ID {branch.branch_id!r}: it is closed and read-only."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchSyncError(
                f"Cannot operate on a branch synchronization with an empty or blank {label}."
            )
