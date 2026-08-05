from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_ownership_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_owner import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwner,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_transfer_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionTransferResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipService:
    """
    Tracks which worker or coordinator currently holds a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session, so
    a long-running session can be safely reassigned without
    interrupting the pipeline run it belongs to.

    The service's responsibility is ownership bookkeeping, not
    execution. It does NOT pause, migrate, or otherwise touch a
    session's runtime state when ownership changes; it relies on the
    existing execution session service, given at construction time,
    only to confirm a session ID is genuinely known, and still
    active, before ownership is assigned or transferred.

    Behavior:
    - A session has exactly one active owner at a time, or none
    - transfer() is atomic: the old owner is replaced by the new one
      as a single operation, never leaving a session momentarily
      unowned or dual-owned
    - Every assignment and transfer is appended to a session's
      ownership history, which release() never erases
    - release() clears a session's active owner; the session is
      unowned until assign() is called again

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known, and to check whether it is still
                active. Any object exposing `session(session_id)`,
                raising if the session is unknown and otherwise
                returning an object with a `status` attribute, is
                accepted
        """

        self._execution_session_service = execution_session_service
        self._active_owner_by_session_id = {}
        self._history_by_session_id = {}
        self._lock = RLock()

    def assign(self, session_id: str, owner_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwner:
        """
        Assign a session's first, or next-after-release, owner.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError:
                If session_id or owner_id is None or blank, the
                execution session service does not recognize
                session_id, or the session already has an active
                owner
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(owner_id, "owner ID")

        with self._lock:
            self._ensure_session_known(session_id)

            if session_id in self._active_owner_by_session_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                    f"Cannot assign session ID {session_id!r}: it already has an active owner. Use transfer() "
                    "instead."
                )

            record = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwner(
                session_id=session_id,
                owner_id=owner_id,
                assigned_at=datetime.now(timezone.utc),
            )

            self._active_owner_by_session_id[session_id] = record
            self._history_by_session_id.setdefault(session_id, []).append(record)

            return record

    def transfer(self, session_id: str, owner_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionTransferResult:
        """
        Atomically reassign a session's active owner.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError:
                If session_id or owner_id is None or blank, the
                execution session service does not recognize
                session_id, the session is not active, the session
                has no active owner, or owner_id is already the
                session's current owner
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(owner_id, "owner ID")

        with self._lock:
            self._ensure_session_active(session_id)

            current = self._active_owner_by_session_id.get(session_id)

            if current is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                    f"Cannot transfer session ID {session_id!r}: it has no active owner. Use assign() instead."
                )

            if current.owner_id == owner_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                    f"Cannot transfer session ID {session_id!r}: owner ID {owner_id!r} is already the current "
                    "owner."
                )

            record = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwner(
                session_id=session_id,
                owner_id=owner_id,
                assigned_at=datetime.now(timezone.utc),
            )

            self._active_owner_by_session_id[session_id] = record
            self._history_by_session_id.setdefault(session_id, []).append(record)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionTransferResult(
                session_id=session_id,
                previous_owner=current.owner_id,
                current_owner=owner_id,
                transferred=True,
            )

    def owner(self, session_id: str):
        """
        Look up a session's current active owner.

        Returns:
            The session's active ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwner,
            or None if it is unowned

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            return self._active_owner_by_session_id.get(session_id)

    def history(self, session_id: str) -> tuple:
        """
        List every owner a session has ever had, in the order
        assigned.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            return tuple(self._history_by_session_id.get(session_id, []))

    def release(self, session_id: str) -> None:
        """
        Clear a session's active owner, without erasing its ownership
        history. Releasing an already-unowned session is not an
        error.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            self._active_owner_by_session_id.pop(session_id, None)

    def _ensure_session_known(self, session_id: str):
        try:
            return self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _ensure_session_active(self, session_id: str):
        session = self._ensure_session_known(session_id)

        if session.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.ACTIVE:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                f"Cannot transfer session ID {session_id!r}: session is {session.status.value}, not active."
            )

        return session

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError(
                f"Cannot operate with an empty or blank {label}."
            )
