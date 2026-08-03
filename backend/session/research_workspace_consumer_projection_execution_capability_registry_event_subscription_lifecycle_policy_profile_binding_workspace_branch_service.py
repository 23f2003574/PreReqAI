from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchService:
    """
    Creates and manages lightweight branches off consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspaces, so multiple feature streams — each
    with its own change sets, reviewed and merged or rebased through
    the existing change set, merge, and rebase workflows — can evolve
    independently before converging.

    The service's responsibility is branch creation, checkout,
    renaming, and closing, not change set creation, review, conflict
    resolution, merging, or rebasing themselves. It does NOT create,
    stage, review, merge, or rebase change sets, or mutate a
    workspace. A branch only records which workspace and revision a
    feature stream started and was last checked out from; every
    change set created while a branch is active still targets the
    branch's underlying workspace ID directly through the existing
    change set service, so it integrates with the change set, merge,
    and rebase workflows without any of them needing to know branches
    exist.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two branches on the same workspace, in any
      state, may share a name
    - Single-active: At most one branch per workspace is ever checked
      out at a time; checking out a branch demotes whichever branch
      was previously active for the same workspace
    - Idempotent on checkout: Checking out the branch that is already
      active refreshes its tracked head revision without demoting or
      promoting anything, and is reported as a no-op
    - Read-only once closed: A closed branch can never be checked out,
      renamed, or closed again
    """

    def __init__(self, workspace_service, workspace_version_service):
        """
        Args:
            workspace_service: The service used to verify a workspace
                exists before a branch is created against it. Any
                object exposing `find(workspace_id)` is accepted
            workspace_version_service: The service used to resolve a
                workspace's latest published revision. Any object
                exposing `latest(workspace_id)`, returning an object
                with a `version` attribute and raising
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError
                when no revision has ever been published, is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError:
                If workspace_service or workspace_version_service is
                None
        """

        for dependency, name in (
            (workspace_service, "workspace service"),
            (workspace_version_service, "workspace version service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                    f"Cannot initialize branch service with a None {name}."
                )

        self._workspace_service = workspace_service
        self._workspace_version_service = workspace_version_service
        self._branches = {}
        self._branch_order_by_workspace = {}
        self._active_by_workspace = {}
        self._lock = RLock()

    def create(
        self,
        workspace_id: str,
        name: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult:
        """
        Create a new, open branch off a workspace's current revision.

        The branch is not automatically checked out; call checkout()
        to make it the workspace's active branch.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError:
                If workspace_id or name is None or blank, no
                workspace is registered under workspace_id, or the
                name is already used by a branch on that workspace
        """

        self._validate_id(workspace_id, "workspace ID")

        if name is None or not name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                "Cannot create a branch with an empty or blank name."
            )

        with self._lock:
            self._resolve_workspace(workspace_id)

            if self._name_taken(workspace_id, name):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                    f"Cannot create a branch: name {name!r} is already used by a branch on workspace ID {workspace_id!r}."
                )

            revision = self._resolve_revision(workspace_id)

            branch = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch(
                branch_id=str(uuid4()),
                workspace_id=workspace_id,
                name=name,
                base_revision=revision,
                head_revision=revision,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.OPEN,
            )

            self._branches[branch.branch_id] = branch
            self._branch_order_by_workspace.setdefault(workspace_id, []).append(branch.branch_id)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult(
                branch=branch,
                successful=True,
            )

    def checkout(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult:
        """
        Check out a branch, making it its workspace's active branch
        and refreshing its tracked head revision to the workspace's
        current one.

        Checking out the branch that is already active is a no-op
        beyond refreshing its head revision; it does not demote or
        promote anything.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError:
                If branch_id is None or blank, no branch is
                registered under it, or the branch is closed
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            branch = self._resolve_branch(branch_id)

            if branch.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.CLOSED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                    f"Cannot checkout branch ID {branch_id!r}: it is closed and read-only."
                )

            already_active = branch.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.ACTIVE

            if not already_active:
                current_active_id = self._active_by_workspace.get(branch.workspace_id)

                if current_active_id is not None:
                    self._branches[current_active_id] = replace(
                        self._branches[current_active_id],
                        status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.OPEN,
                    )

            updated = replace(
                branch,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.ACTIVE,
                head_revision=self._resolve_revision(branch.workspace_id),
            )

            self._branches[branch_id] = updated
            self._active_by_workspace[branch.workspace_id] = branch_id

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult(
                branch=updated,
                successful=not already_active,
            )

    def rename(
        self,
        branch_id: str,
        name: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult:
        """
        Rename a branch that is not closed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError:
                If branch_id or name is None or blank, no branch is
                registered under branch_id, the branch is closed, or
                the name is already used by another branch on the
                same workspace
        """

        self._validate_id(branch_id, "branch ID")

        if name is None or not name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                "Cannot rename a branch to an empty or blank name."
            )

        with self._lock:
            branch = self._resolve_branch(branch_id)

            if branch.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.CLOSED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                    f"Cannot rename branch ID {branch_id!r}: it is closed and read-only."
                )

            if name != branch.name and self._name_taken(branch.workspace_id, name):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                    f"Cannot rename a branch: name {name!r} is already used by a branch on workspace ID "
                    f"{branch.workspace_id!r}."
                )

            renamed = replace(branch, name=name)
            self._branches[branch_id] = renamed

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult(
                branch=renamed,
                successful=True,
            )

    def close(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult:
        """
        Close a branch, making it permanently read-only.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError:
                If branch_id is None or blank, no branch is
                registered under it, it is already closed, or it is
                the workspace's active branch
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            branch = self._resolve_branch(branch_id)

            if branch.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.CLOSED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                    f"Cannot close branch ID {branch_id!r}: it is already closed."
                )

            if branch.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.ACTIVE:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                    f"Cannot close branch ID {branch_id!r}: it is the active branch for workspace ID "
                    f"{branch.workspace_id!r}; checkout another branch first."
                )

            closed = replace(
                branch,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchStatus.CLOSED,
            )
            self._branches[branch_id] = closed

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchResult(
                branch=closed,
                successful=True,
            )

    def active_branch(self, workspace_id: str):
        """
        Find the branch currently checked out for a workspace.

        Returns:
            The active branch, or None if no branch is currently
            checked out for the workspace

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError:
                If workspace_id is None or blank, or no workspace is
                registered under it
        """

        self._validate_id(workspace_id, "workspace ID")

        with self._lock:
            self._resolve_workspace(workspace_id)

            branch_id = self._active_by_workspace.get(workspace_id)

            return self._branches.get(branch_id) if branch_id is not None else None

    def list(self, workspace_id: str) -> tuple:
        """
        List every branch ever created for a workspace, including
        closed ones, in the order they were created.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError:
                If workspace_id is None or blank, or no workspace is
                registered under it
        """

        self._validate_id(workspace_id, "workspace ID")

        with self._lock:
            self._resolve_workspace(workspace_id)

            branch_ids = self._branch_order_by_workspace.get(workspace_id, ())

            return tuple(self._branches[branch_id] for branch_id in branch_ids)

    def find(self, branch_id: str):
        """
        Find the branch registered under a branch ID.

        Returns:
            The matching branch, or None if no branch is registered
            under it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError:
                If branch_id is None or blank
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            return self._branches.get(branch_id)

    def _name_taken(self, workspace_id: str, name: str) -> bool:
        branch_ids = self._branch_order_by_workspace.get(workspace_id, ())

        return any(self._branches[branch_id].name == name for branch_id in branch_ids)

    def _resolve_revision(self, workspace_id: str):
        try:
            return self._workspace_version_service.latest(workspace_id).version
        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError:
            return None

    def _resolve_workspace(self, workspace_id: str):
        workspace = self._workspace_service.find(workspace_id)

        if workspace is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                f"Cannot operate on a branch: no workspace is registered under workspace ID {workspace_id!r}."
            )

        return workspace

    def _resolve_branch(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranch:
        branch = self._branches.get(branch_id)

        if branch is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                f"Cannot operate on a branch: no branch is registered under branch ID {branch_id!r}."
            )

        return branch

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchError(
                f"Cannot operate on a branch with an empty or blank {label}."
            )
