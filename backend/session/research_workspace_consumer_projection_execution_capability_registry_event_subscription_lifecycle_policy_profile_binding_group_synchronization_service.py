from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_sync_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_sync_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSynchronizationService:
    """
    Keeps consumer projection execution capability registry event
    subscription lifecycle policy profile binding groups
    synchronized across registries, deployment targets, and runtime
    caches after group updates or releases.

    The service's responsibility is queuing and applying
    synchronization requests, not group creation, membership
    management, deployment, or release management themselves. It
    does NOT create groups, mutate group membership, deploy groups,
    persist synchronization state externally, log, or publish
    events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Idempotent: Queuing a synchronization for a target that is
      already up to date is a no-op; queuing the same (group, target)
      pair twice while one is already pending is rejected
    - Change-aware: A target is only queued when the group's current
      member bindings differ from what was last successfully
      synchronized to it
    - Retriable: A target that fails to synchronize remains eligible
      to be queued and applied again, without disturbing targets that
      already succeeded
    - Immutable-result: Every call returns a new, immutable result; no
      result is ever mutated
    """

    def __init__(self, group_registry, target_gateway):
        """
        Args:
            group_registry: The registry used to resolve a group's
                current member bindings. Any object exposing
                `find(group_id)`, returning an object with a
                `binding_ids` collection, is accepted
            target_gateway: The gateway used to apply a queued
                synchronization to its target. Any object exposing
                `push(group_id, target)`, returning True on success
                and False on failure, is accepted
        """

        if group_registry is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError(
                "Cannot initialize synchronization service with a None group registry."
            )

        if target_gateway is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError(
                "Cannot initialize synchronization service with a None target gateway."
            )

        self._group_registry = group_registry
        self._target_gateway = target_gateway
        self._pending = ()
        self._synchronized_state = {}
        self._known_targets = {}
        self._failed_targets = {}
        self._lock = RLock()

    def sync_target(
        self,
        group_id: str,
        target: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult:
        """
        Queue a synchronization of a group's current state to a
        single target.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError:
                If the group ID or target is None or blank, no group
                is registered under the group ID, or a synchronization
                for the same group and target is already pending
        """

        self._validate_identifier(group_id, "group ID")
        self._validate_identifier(target, "target")

        with self._lock:
            group = self._resolve_group(group_id)

            if any(
                pending.group_id == group_id and pending.target == target
                for pending in self._pending
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError(
                    f"A synchronization for group ID {group_id!r} and target {target!r} is already pending."
                )

            if self._is_up_to_date(group_id, target, group):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                    failed_targets=(),
                )

            request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncRequest(
                group_id=group_id,
                operation="register",
                target=target,
            )

            self._pending = self._pending + (request,)
            self._known_targets.setdefault(group_id, set()).add(target)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult(
                synchronized=True,
                synchronized_targets=(target,),
                failed_targets=(),
            )

    def sync(
        self,
        group_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult:
        """
        Queue a synchronization of a group's current state to every
        target it has previously been associated with, including any
        that are currently pending retry after a prior failure.

        Groups that have never been associated with a target have
        nothing to synchronize, so calling this is a no-op for them.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError:
                If the group ID is None or blank, or no group is
                registered under it
        """

        self._validate_identifier(group_id, "group ID")

        with self._lock:
            self._resolve_group(group_id)

            targets = set(self._known_targets.get(group_id, set())) | set(
                self._failed_targets.get(group_id, set())
            )

        synchronized_targets = []

        for target in sorted(targets):
            result = self.sync_target(group_id, target)
            synchronized_targets.extend(result.synchronized_targets)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult(
            synchronized=bool(synchronized_targets),
            synchronized_targets=tuple(synchronized_targets),
            failed_targets=(),
        )

    def sync_all(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult:
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
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                    failed_targets=(),
                )

            pending_requests = self._pending
            self._pending = ()

            synchronized_targets = []
            failed_targets = []

            for request in pending_requests:
                if self._target_gateway.push(request.group_id, request.target):
                    group = self._group_registry.find(request.group_id)

                    self._synchronized_state[(request.group_id, request.target)] = tuple(
                        group.binding_ids
                    )
                    self._failed_targets.get(request.group_id, set()).discard(request.target)

                    synchronized_targets.append(request.target)
                else:
                    self._failed_targets.setdefault(request.group_id, set()).add(request.target)

                    failed_targets.append(request.target)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncResult(
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

    def is_synchronized(self, group_id: str) -> bool:
        """
        Check whether a group is fully synchronized: it has at least
        one target it has been synchronized to, and no target is
        currently pending or failed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError:
                If the group ID is None or blank
        """

        self._validate_identifier(group_id, "group ID")

        with self._lock:
            if self._failed_targets.get(group_id):
                return False

            if any(pending.group_id == group_id for pending in self._pending):
                return False

            return bool(self._known_targets.get(group_id))

    def _is_up_to_date(self, group_id: str, target: str, group) -> bool:
        return self._synchronized_state.get((group_id, target)) == tuple(group.binding_ids)

    def _resolve_group(self, group_id: str):
        group = self._group_registry.find(group_id)

        if group is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError(
                f"Cannot synchronize: no group is registered under group ID {group_id!r}."
            )

        return group

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupSyncError(
                f"Cannot synchronize with an empty or blank {label}."
            )
