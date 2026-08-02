from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_sync_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_sync_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSynchronizationService:
    """
    Keeps consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspaces —
    including their current definition, published versions, and
    release metadata — synchronized across registries, deployment
    targets, and runtime caches after workspace updates,
    publications, or releases.

    The service's responsibility is queuing and applying
    synchronization requests, not workspace creation, membership
    management, version publication, release management, or
    deployment themselves. It does NOT create workspaces, mutate
    workspace membership, publish versions, release or retire
    versions, deploy workspaces, persist synchronization state
    externally, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Idempotent: Queuing a synchronization for a target that is
      already up to date is a no-op; queuing the same (workspace,
      target) pair twice while one is already pending is rejected
    - Change-aware: A target is only queued when the workspace's
      current definition, latest published version, or latest
      released version differs from what was last successfully
      synchronized to it
    - Retriable: A target that fails to synchronize remains eligible
      to be queued and applied again, without disturbing targets that
      already succeeded
    - Immutable-result: Every call returns a new, immutable result; no
      result is ever mutated
    """

    def __init__(
        self,
        workspace_registry,
        workspace_version_service,
        release_service,
        target_gateway,
    ):
        """
        Args:
            workspace_registry: The registry used to resolve a
                workspace's current definition. Any object exposing
                `find(workspace_id)`, returning an object with
                `binding_ids`, `template_ids`, `preset_ids`, and
                `group_ids` collections, is accepted
            workspace_version_service: The service used to resolve a
                workspace's latest published version. Any object
                exposing `latest(workspace_id)` is accepted
            release_service: The service used to resolve a
                workspace's latest released version. Any object
                exposing `latest_release(workspace_id)` is accepted
            target_gateway: The gateway used to apply a queued
                synchronization to its target. Any object exposing
                `push(workspace_id, target)`, returning True on
                success and False on failure, is accepted
        """

        for dependency, name in (
            (workspace_registry, "workspace registry"),
            (workspace_version_service, "workspace version service"),
            (release_service, "release service"),
            (target_gateway, "target gateway"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError(
                    f"Cannot initialize synchronization service with a None {name}."
                )

        self._workspace_registry = workspace_registry
        self._workspace_version_service = workspace_version_service
        self._release_service = release_service
        self._target_gateway = target_gateway
        self._pending = ()
        self._synchronized_state = {}
        self._known_targets = {}
        self._failed_targets = {}
        self._lock = RLock()

    def sync_target(
        self,
        workspace_id: str,
        target: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult:
        """
        Queue a synchronization of a workspace's current state to a
        single target.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError:
                If the workspace ID or target is None or blank, no
                workspace is registered under the workspace ID, or a
                synchronization for the same workspace and target is
                already pending
        """

        self._validate_identifier(workspace_id, "workspace ID")
        self._validate_identifier(target, "target")

        with self._lock:
            workspace = self._resolve_workspace(workspace_id)

            if any(
                pending.workspace_id == workspace_id and pending.target == target
                for pending in self._pending
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError(
                    f"A synchronization for workspace ID {workspace_id!r} and target {target!r} is already pending."
                )

            if self._is_up_to_date(workspace_id, target, workspace):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                    failed_targets=(),
                )

            request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncRequest(
                workspace_id=workspace_id,
                operation="register",
                target=target,
            )

            self._pending = self._pending + (request,)
            self._known_targets.setdefault(workspace_id, set()).add(target)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult(
                synchronized=True,
                synchronized_targets=(target,),
                failed_targets=(),
            )

    def sync(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult:
        """
        Queue a synchronization of a workspace's current state to
        every target it has previously been associated with,
        including any that are currently pending retry after a prior
        failure.

        Workspaces that have never been associated with a target have
        nothing to synchronize, so calling this is a no-op for them.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError:
                If the workspace ID is None or blank, or no workspace
                is registered under it
        """

        self._validate_identifier(workspace_id, "workspace ID")

        with self._lock:
            self._resolve_workspace(workspace_id)

            targets = set(self._known_targets.get(workspace_id, set())) | set(
                self._failed_targets.get(workspace_id, set())
            )

        synchronized_targets = []

        for target in sorted(targets):
            result = self.sync_target(workspace_id, target)
            synchronized_targets.extend(result.synchronized_targets)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult(
            synchronized=bool(synchronized_targets),
            synchronized_targets=tuple(synchronized_targets),
            failed_targets=(),
        )

    def sync_all(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult:
        """
        Apply every pending synchronization request.

        A target whose synchronization fails is recorded as failed
        and remains eligible to be queued and applied again; it does
        not block other targets from being applied.

        Returns:
            An immutable result carrying every target that was
            successfully synchronized and every target that failed,
            in the order the requests were queued
        """

        with self._lock:
            if not self._pending:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                    failed_targets=(),
                )

            pending_requests = self._pending
            self._pending = ()

            synchronized_targets = []
            failed_targets = []

            for request in pending_requests:
                if self._target_gateway.push(request.workspace_id, request.target):
                    workspace = self._workspace_registry.find(request.workspace_id)

                    self._synchronized_state[(request.workspace_id, request.target)] = self._snapshot(
                        request.workspace_id, workspace
                    )
                    self._failed_targets.get(request.workspace_id, set()).discard(request.target)

                    synchronized_targets.append(request.target)
                else:
                    self._failed_targets.setdefault(request.workspace_id, set()).add(request.target)

                    failed_targets.append(request.target)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncResult(
                synchronized=bool(synchronized_targets),
                synchronized_targets=tuple(synchronized_targets),
                failed_targets=tuple(failed_targets),
            )

    def pending(self) -> tuple:
        """
        List every synchronization request queued but not yet
        applied, preserving the order they were queued.
        """

        with self._lock:
            return self._pending

    def is_synchronized(self, workspace_id: str) -> bool:
        """
        Check whether a workspace is fully synchronized: it has at
        least one target it has been synchronized to, and no target
        is currently pending or failed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError:
                If the workspace ID is None or blank
        """

        self._validate_identifier(workspace_id, "workspace ID")

        with self._lock:
            if self._failed_targets.get(workspace_id):
                return False

            if any(pending.workspace_id == workspace_id for pending in self._pending):
                return False

            return bool(self._known_targets.get(workspace_id))

    def _is_up_to_date(self, workspace_id: str, target: str, workspace) -> bool:
        return self._synchronized_state.get((workspace_id, target)) == self._snapshot(workspace_id, workspace)

    def _snapshot(self, workspace_id: str, workspace) -> tuple:
        try:
            version_id = self._workspace_version_service.latest(workspace_id).version
        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionError:
            version_id = None

        latest_release = self._release_service.latest_release(workspace_id)
        released_version = latest_release.version if latest_release is not None else None

        return (
            tuple(workspace.binding_ids),
            tuple(workspace.template_ids),
            tuple(workspace.preset_ids),
            tuple(workspace.group_ids),
            version_id,
            released_version,
        )

    def _resolve_workspace(self, workspace_id: str):
        workspace = self._workspace_registry.find(workspace_id)

        if workspace is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError(
                f"Cannot synchronize: no workspace is registered under workspace ID {workspace_id!r}."
            )

        return workspace

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSyncError(
                f"Cannot synchronize with an empty or blank {label}."
            )
