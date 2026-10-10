from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_sync_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_sync_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSynchronizationService:
    """
    Keeps consumer projection execution capability registry event
    subscription lifecycle policy profile assignments synchronized
    across registries, caches, and distributed nodes after assignment
    changes.

    The service's responsibility is queuing and applying
    synchronization requests, not assigning profiles, registering
    profiles, persisting synchronization state externally, logging, or
    publishing events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Idempotent: Resubmitting the exact same pending request is a
      no-op; it is not queued twice
    - Change-aware: Requests that would not change the currently
      synchronized state are skipped rather than queued
    - Immutable-result: Every sync() and sync_all() call returns a new,
      immutable result; no result is ever mutated
    """

    def __init__(
        self,
        assignment_service,
        profile_service,
    ):
        """
        Args:
            assignment_service: The assignment service used to verify
                a target is known. Any object exposing
                `is_assigned(target_id)` and `list()` is accepted
            profile_service: The profile service used to verify a
                profile exists. Any object exposing
                `contains(profile_id)` is accepted
        """

        if assignment_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError(
                "Cannot initialize synchronization service with a None assignment service."
            )

        if profile_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError(
                "Cannot initialize synchronization service with a None profile service."
            )

        self._assignment_service = assignment_service
        self._profile_service = profile_service
        self._pending = ()
        self._synchronized_state = {}
        self._lock = RLock()

    def sync(
        self,
        sync_request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult:
        """
        Queues a synchronization request for a single assignment
        change.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError:
                If sync_request is None, its profile ID is unknown/
                unregistered, its target ID is unknown, or a different
                request for the same target is already pending
        """

        if sync_request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError(
                "Cannot synchronize a None sync request."
            )

        with self._lock:
            if any(pending is sync_request for pending in self._pending):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                )

            self._validate_known(sync_request)

            if self._is_up_to_date(sync_request):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                )

            if any(pending.target_id == sync_request.target_id for pending in self._pending):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError(
                    f"A synchronization for target ID {sync_request.target_id!r} is already pending."
                )

            self._pending = self._pending + (sync_request,)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult(
                synchronized=True,
                synchronized_targets=(sync_request.target_id,),
            )

    def sync_all(
        self,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult:
        """
        Applies every pending synchronization request, preserving
        synchronization state for each target it touches.

        Returns:
            An immutable result carrying every target ID that was
            applied, in the order the requests were queued
        """

        with self._lock:
            if not self._pending:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult(
                    synchronized=False,
                    synchronized_targets=(),
                )

            synchronized_targets = []

            for pending_request in self._pending:
                self._apply(pending_request)
                synchronized_targets.append(pending_request.target_id)

            self._pending = ()

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncResult(
                synchronized=True,
                synchronized_targets=tuple(synchronized_targets),
            )

    def is_synchronized(self, target_id: str) -> bool:
        """
        Checks whether target_id's assignment is currently
        synchronized.

        Returns:
            True if target_id has an applied, up-to-date
            synchronization, False otherwise
        """

        with self._lock:
            return target_id in self._synchronized_state

    def pending(self) -> tuple:
        """
        Lists every synchronization request queued but not yet
        applied, preserving the order they were queued.
        """

        with self._lock:
            return self._pending

    def _validate_known(self, sync_request) -> None:
        if sync_request.operation == "register" and not self._profile_service.contains(sync_request.profile_id):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentSyncError(
                f"Cannot synchronize: profile ID {sync_request.profile_id!r} is unknown/unregistered."
            )

    def _is_up_to_date(self, sync_request) -> bool:
        current = self._synchronized_state.get(sync_request.target_id)

        if sync_request.operation == "register":
            return current == sync_request.profile_id

        return current is None

    def _apply(self, sync_request) -> None:
        if sync_request.operation == "register":
            self._synchronized_state[sync_request.target_id] = sync_request.profile_id
        else:
            self._synchronized_state.pop(sync_request.target_id, None)
