from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_rebase import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebase,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_rebase_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebaseStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_conflict_resolution_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_rebase_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_rebase_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseService:
    """
    Rebases stale consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    change sets onto their workspace's latest published revision, so
    conflicts are caught and minimized before review and approval
    rather than discovered only at merge or apply time.

    The service's responsibility is staleness detection, replay, and
    conflict re-checking, not change set creation, operation staging,
    review, conflict resolution, or revision publication themselves.
    It does NOT create or mutate a change set's operations, approve or
    reject reviews, resolve conflicts, publish workspace revisions, or
    mutate a workspace. It operates over a change set service, a
    workspace version service, and a conflict service supplied at
    construction time.

    A change set's operations are always position-independent member
    additions and removals, so replaying them onto a new revision
    never needs to transform their content; only their continued
    validity is re-checked. A change set that has never been rebased
    is presumed to be at its workspace's revision as of its most
    recent successful rebase check, so its first rebase always
    attempts to validate it against the latest published revision.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Order-preserving: A rebased change set's operations are
      returned in their original order, unchanged
    - Conflict-aware: Every rebase reuses conflict detection against
      the change set's current, live workspace state; any unresolved
      conflict blocks the rebase without advancing its tracked
      revision
    - Non-destructive on preview: Previewing a rebase never advances
      the change set's tracked revision, flags it for re-review, or
      records rebase history
    - History-retaining: Every rebase attempt, successful or not,
      remains retrievable per workspace
    - Review-invalidating: A successful, non-no-op rebase always flags
      its change set as requiring a fresh review, since reviewers who
      approved it did so against an older revision
    """

    def __init__(self, change_set_service, workspace_version_service, conflict_service):
        """
        Args:
            change_set_service: The service used to resolve a change
                set's workspace ID, status, and operations. Any object
                exposing `find(change_set_id)` is accepted
            workspace_version_service: The service used to resolve a
                workspace's latest published revision. Any object
                exposing `latest(workspace_id)`, returning an object
                with a `version` attribute and raising
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError
                when no revision has ever been published, is accepted
            conflict_service: The service used to detect conflicts on
                a change set before rebasing. Any object exposing
                `detect(change_set_id)` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError:
                If change_set_service, workspace_version_service, or
                conflict_service is None
        """

        for dependency, name in (
            (change_set_service, "change set service"),
            (workspace_version_service, "workspace version service"),
            (conflict_service, "conflict service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                    f"Cannot initialize rebase service with a None {name}."
                )

        self._change_set_service = change_set_service
        self._workspace_version_service = workspace_version_service
        self._conflict_service = conflict_service
        self._revision_by_change_set = {}
        self._review_required = set()
        self._rebases = {}
        self._rebase_order_by_workspace = {}
        self._lock = RLock()

    def rebase(
        self,
        change_set_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseResult:
        """
        Rebase a change set onto its workspace's latest published
        revision.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError:
                If change_set_id is None or blank, no change set is
                registered under it, the change set is not open, no
                revision has ever been published for its workspace, or
                the change set is already at the current revision

        Returns:
            A result carrying the replayed operations on success, or
            the unresolved conflicts that blocked the rebase on
            failure. The change set's tracked revision only advances,
            and re-review is only required, when the rebase succeeds
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)
            self._require_open(change_set)

            target_revision = self._resolve_target_revision(change_set.workspace_id)
            source_revision = self._revision_by_change_set.get(change_set_id)

            if source_revision is not None and source_revision == target_revision:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                    f"Cannot rebase change set ID {change_set_id!r}: it is already at the current revision "
                    f"{target_revision!r}."
                )

            conflicts = self._detect_unresolved_conflicts(change_set_id)

            rebase_record = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebase(
                rebase_id=str(uuid4()),
                change_set_id=change_set_id,
                source_revision=source_revision,
                target_revision=target_revision,
                status=(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebaseStatus.FAILED
                    if conflicts
                    else ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebaseStatus.SUCCEEDED
                ),
            )

            self._rebases[rebase_record.rebase_id] = rebase_record
            self._rebase_order_by_workspace.setdefault(change_set.workspace_id, []).append(rebase_record.rebase_id)

            if conflicts:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseResult(
                    successful=False,
                    rebased_operations=(),
                    conflicts=conflicts,
                )

            self._revision_by_change_set[change_set_id] = target_revision
            self._review_required.add(change_set_id)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseResult(
                successful=True,
                rebased_operations=change_set.operations,
                conflicts=(),
            )

    def can_rebase(self, change_set_id: str) -> bool:
        """
        Check whether rebasing a change set would currently succeed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError:
                If change_set_id is None or blank, no change set is
                registered under it, or no revision has ever been
                published for its workspace
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)

            if change_set.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
                return False

            target_revision = self._resolve_target_revision(change_set.workspace_id)
            source_revision = self._revision_by_change_set.get(change_set_id)

            if source_revision is not None and source_revision == target_revision:
                return False

            return not self._detect_unresolved_conflicts(change_set_id)

    def preview_rebase(
        self,
        change_set_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseResult:
        """
        Compute the result a rebase of a change set would currently
        produce, without advancing its tracked revision, flagging it
        for re-review, or recording rebase history.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError:
                If change_set_id is None or blank, no change set is
                registered under it, the change set is not open, no
                revision has ever been published for its workspace, or
                the change set is already at the current revision
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            change_set = self._resolve_change_set(change_set_id)
            self._require_open(change_set)

            target_revision = self._resolve_target_revision(change_set.workspace_id)
            source_revision = self._revision_by_change_set.get(change_set_id)

            if source_revision is not None and source_revision == target_revision:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                    f"Cannot preview a rebase for change set ID {change_set_id!r}: it is already at the current "
                    f"revision {target_revision!r}."
                )

            conflicts = self._detect_unresolved_conflicts(change_set_id)

            if conflicts:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseResult(
                    successful=False,
                    rebased_operations=(),
                    conflicts=conflicts,
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseResult(
                successful=True,
                rebased_operations=change_set.operations,
                conflicts=(),
            )

    def rebase_history(self, workspace_id: str) -> tuple:
        """
        List every rebase attempt recorded for a workspace, including
        failed ones, in the order they were attempted.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError:
                If workspace_id is None or blank
        """

        self._validate_id(workspace_id, "workspace ID")

        with self._lock:
            rebase_ids = self._rebase_order_by_workspace.get(workspace_id, ())

            return tuple(self._rebases[rebase_id] for rebase_id in rebase_ids)

    def requires_review(self, change_set_id: str) -> bool:
        """
        Check whether a change set has been flagged as requiring a
        fresh review since its last successful rebase.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError:
                If change_set_id is None or blank
        """

        self._validate_id(change_set_id, "change set ID")

        with self._lock:
            return change_set_id in self._review_required

    def find(self, rebase_id: str):
        """
        Find the rebase record registered under a rebase ID.

        Returns:
            The matching rebase record, or None if no rebase is
            registered under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError:
                If rebase_id is None or blank
        """

        self._validate_id(rebase_id, "rebase ID")

        with self._lock:
            return self._rebases.get(rebase_id)

    def _detect_unresolved_conflicts(self, change_set_id: str) -> tuple:
        return tuple(
            conflict
            for conflict in self._conflict_service.detect(change_set_id)
            if conflict.resolution_status
            == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictResolutionStatus.UNRESOLVED
        )

    def _resolve_target_revision(self, workspace_id: str) -> str:
        try:
            return self._workspace_version_service.latest(workspace_id).version
        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                f"Cannot rebase: no revision has ever been published for workspace ID {workspace_id!r}."
            )

    def _resolve_change_set(self, change_set_id: str):
        change_set = self._change_set_service.find(change_set_id)

        if change_set is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                f"Cannot operate on a rebase: no change set is registered under change set ID {change_set_id!r}."
            )

        return change_set

    def _require_open(self, change_set) -> None:
        if change_set.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus.OPEN:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                f"Cannot rebase change set ID {change_set.change_set_id!r}: it is {change_set.status.value}, not open."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                f"Cannot operate on a rebase with an empty or blank {label}."
            )
