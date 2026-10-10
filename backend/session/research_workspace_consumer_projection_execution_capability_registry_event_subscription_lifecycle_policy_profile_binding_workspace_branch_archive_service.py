from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_archive import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchive,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_archive_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_recovery_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchRecoveryResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveService:
    """
    Archives and restores consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace branches, so completed or inactive branches can be set
    aside while their complete history remains available for future
    inspection or restoration.

    The service's responsibility is archiving, restoring, and
    tracking archive state, not branch creation, checkout, renaming,
    or closing themselves. It does NOT create, checkout, rename, or
    close a branch, or mutate its revisions in any way. Archiving
    never closes or otherwise mutates the underlying branch — it is
    tracked entirely independently, which is what makes restoring
    possible: a restored branch's workspace, name, revisions, and
    status are exactly as they were, since archiving never touched
    them. Other workflows (change set creation, review, merge,
    rebase, synchronization) integrate with archiving by consulting
    is_archived() before proceeding; this service never reaches into
    them itself.

    "Read-only" and "excluded from active workflows" are advisory
    guarantees enforced by callers consulting is_archived(), not by
    this service reaching into other services to block them.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Re-archivable: A branch may be archived, restored, and archived
      again any number of times; each archiving produces a new,
      distinct archive record
    - Current-list-accurate: archives() reports only branches
      currently archived; a restored branch no longer appears there
    - History-retaining: Every archive record ever produced for a
      branch remains retrievable through history(), including ones
      superseded by a later restoration
    """

    def __init__(self, branch_service):
        """
        Args:
            branch_service: The service used to resolve a branch's
                status and to list every branch on a workspace. Any
                object exposing `find(branch_id)` and
                `list(workspace_id)` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError:
                If branch_service is None
        """

        if branch_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                "Cannot initialize branch archive service with a None branch service."
            )

        self._branch_service = branch_service
        self._archives = {}
        self._archive_order_by_branch = {}
        self._currently_archived = {}
        self._lock = RLock()

    def archive(
        self,
        branch_id: str,
        reason: str | None = None,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchive:
        """
        Archive a branch.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError:
                If branch_id is None or blank, no branch is registered
                under it, it is the workspace's currently active
                (default) branch, or it is already archived
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            branch = self._resolve_branch(branch_id)

            if branch.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.ACTIVE:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                    f"Cannot archive branch ID {branch_id!r}: it is the active default branch for workspace ID "
                    f"{branch.workspace_id!r}; checkout another branch first."
                )

            if branch_id in self._currently_archived:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                    f"Cannot archive branch ID {branch_id!r}: it is already archived."
                )

            record = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchive(
                archive_id=str(uuid4()),
                branch_id=branch_id,
                archived_at=datetime.now(timezone.utc),
                reason=reason,
            )

            self._archives[record.archive_id] = record
            self._archive_order_by_branch.setdefault(branch_id, []).append(record.archive_id)
            self._currently_archived[branch_id] = record.archive_id

            return record

    def restore(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchRecoveryResult:
        """
        Restore a currently archived branch.

        The underlying branch was never mutated by archiving, so it
        resumes exactly as it was — same workspace, name, status, and
        revisions.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError:
                If branch_id is None or blank, no branch is registered
                under it, or it is not currently archived
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            self._resolve_branch(branch_id)

            if branch_id not in self._currently_archived:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                    f"Cannot restore branch ID {branch_id!r}: it is not currently archived."
                )

            del self._currently_archived[branch_id]

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchRecoveryResult(
                branch_id=branch_id,
                recovered=True,
                recovered_at=datetime.now(timezone.utc),
            )

    def archives(self, workspace_id: str) -> tuple:
        """
        List the archive record of every branch on a workspace that
        is currently archived, in the order the branches were
        created. A branch that has been restored does not appear
        here.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError:
                If workspace_id is None or blank, or no workspace is
                registered under it
        """

        self._validate_id(workspace_id, "workspace ID")

        with self._lock:
            branches = self._resolve_branches(workspace_id)

            return tuple(
                self._archives[self._currently_archived[branch.branch_id]]
                for branch in branches
                if branch.branch_id in self._currently_archived
            )

    def is_archived(self, branch_id: str) -> bool:
        """
        Check whether a branch is currently archived.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError:
                If branch_id is None or blank, or no branch is
                registered under it
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            self._resolve_branch(branch_id)

            return branch_id in self._currently_archived

    def history(self, branch_id: str) -> tuple:
        """
        List every archive record ever produced for a branch,
        including ones superseded by a later restoration, in the
        order they were produced.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError:
                If branch_id is None or blank, or no branch is
                registered under it
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            self._resolve_branch(branch_id)

            archive_ids = self._archive_order_by_branch.get(branch_id, ())

            return tuple(self._archives[archive_id] for archive_id in archive_ids)

    def find(self, archive_id: str):
        """
        Find the archive record registered under an archive ID.

        Returns:
            The matching archive record, or None if no archive is
            registered under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError:
                If archive_id is None or blank
        """

        self._validate_id(archive_id, "archive ID")

        with self._lock:
            return self._archives.get(archive_id)

    def _resolve_branch(self, branch_id: str):
        branch = self._branch_service.find(branch_id)

        if branch is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                f"Cannot operate on a branch archive: no branch is registered under branch ID {branch_id!r}."
            )

        return branch

    def _resolve_branches(self, workspace_id: str) -> tuple:
        try:
            return self._branch_service.list(workspace_id)
        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                str(error)
            ) from error

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchArchiveError(
                f"Cannot operate on a branch archive with an empty or blank {label}."
            )
