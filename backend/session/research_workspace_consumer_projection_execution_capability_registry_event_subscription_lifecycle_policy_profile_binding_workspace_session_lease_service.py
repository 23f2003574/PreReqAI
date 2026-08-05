from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_lease_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_lease import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLease,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_lease_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseService:
    """
    Grants time-boxed leases on consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution sessions, so an abandoned or
    disconnected worker's claim lapses automatically instead of
    permanently blocking a session's execution ownership.

    The service's responsibility is lease exclusivity and expiry, not
    ownership itself. It does NOT assign, transfer, or release
    execution ownership; a caller is expected to hold a currently
    active lease, confirmed through owner() or a successful acquire()
    or renew(), before it changes a session's ownership through a
    session ownership service.

    Behavior:
    - At most one active lease may exist per session at a time;
      acquire() rejects a session that already has one, unless that
      lease has itself expired
    - renew() extends an active lease's expiration; it cannot revive
      a lease that has already expired
    - A lease past its expires_at is treated as no longer active:
      owner() disregards it, and expired() releases it automatically
    - release() and expired() both report the same outcome shape:
      the lease is no longer active

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service, lease_duration_seconds: float = 60.0):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known before a lease is acquired for
                it. Any object exposing `session(session_id)`,
                raising if the session is unknown, is accepted
            lease_duration_seconds: How long, in seconds, a lease
                remains active after being acquired or renewed

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError:
                If lease_duration_seconds is not a positive number
        """

        if (
            lease_duration_seconds is None
            or isinstance(lease_duration_seconds, bool)
            or not isinstance(lease_duration_seconds, (int, float))
            or lease_duration_seconds <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                "Cannot build a session lease service with a non-positive lease_duration_seconds."
            )

        self._execution_session_service = execution_session_service
        self._lease_duration = timedelta(seconds=lease_duration_seconds)
        self._leases = {}
        self._active_lease_id_by_session_id = {}
        self._lock = RLock()

    def acquire(self, session_id: str, holder_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLease:
        """
        Acquire a new lease on a session for a holder.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError:
                If session_id or holder_id is None or blank, the
                execution session service does not recognize
                session_id, or the session already has an active
                lease
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(holder_id, "holder ID")

        with self._lock:
            self._ensure_session_known(session_id)

            existing_lease_id = self._active_lease_id_by_session_id.get(session_id)

            if existing_lease_id is not None:
                if self._is_active(self._leases[existing_lease_id]):
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                        f"Cannot acquire a lease for session ID {session_id!r}: it already has an active lease."
                    )

                self._forget(existing_lease_id)

            now = datetime.now(timezone.utc)

            lease = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLease(
                lease_id=str(uuid4()),
                session_id=session_id,
                holder_id=holder_id,
                acquired_at=now,
                expires_at=now + self._lease_duration,
            )

            self._leases[lease.lease_id] = lease
            self._active_lease_id_by_session_id[session_id] = lease.lease_id

            return lease

    def renew(self, lease_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLease:
        """
        Extend an active lease's expiration.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError:
                If lease_id is None or blank, no lease is registered
                under it, or the lease has already expired
        """

        self._validate_id(lease_id, "lease ID")

        with self._lock:
            lease = self._resolve(lease_id)

            if not self._is_active(lease):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                    f"Cannot renew lease ID {lease_id!r}: it has already expired. Use acquire() instead."
                )

            renewed = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLease(
                lease_id=lease.lease_id,
                session_id=lease.session_id,
                holder_id=lease.holder_id,
                acquired_at=lease.acquired_at,
                expires_at=datetime.now(timezone.utc) + self._lease_duration,
            )

            self._leases[lease_id] = renewed

            return renewed

    def release(self, lease_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseResult:
        """
        Release a lease, freeing its session immediately.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError:
                If lease_id is None or blank, or no lease is
                registered under it
        """

        self._validate_id(lease_id, "lease ID")

        with self._lock:
            self._resolve(lease_id)

            self._forget(lease_id)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseResult(
                lease_id=lease_id,
                active=False,
            )

    def expired(self) -> tuple:
        """
        Release every lease past its expires_at, automatically.

        Returns:
            A ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseResult
            for each lease that was released
        """

        with self._lock:
            stale = tuple(lease for lease in self._leases.values() if not self._is_active(lease))

            results = tuple(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseResult(
                    lease_id=lease.lease_id,
                    active=False,
                )
                for lease in stale
            )

            for lease in stale:
                self._forget(lease.lease_id)

            return results

    def owner(self, session_id: str):
        """
        Look up the lease currently active on a session, if any.

        Returns:
            The session's active ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLease,
            or None if it is unleased or its lease has expired

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError:
                If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            lease_id = self._active_lease_id_by_session_id.get(session_id)

            if lease_id is None:
                return None

            lease = self._leases[lease_id]

            if not self._is_active(lease):
                return None

            return lease

    def _is_active(self, lease: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLease) -> bool:
        return lease.expires_at > datetime.now(timezone.utc)

    def _forget(self, lease_id: str) -> None:
        lease = self._leases.pop(lease_id, None)

        if lease is None:
            return

        if self._active_lease_id_by_session_id.get(lease.session_id) == lease_id:
            del self._active_lease_id_by_session_id[lease.session_id]

    def _ensure_session_known(self, session_id: str) -> None:
        try:
            self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _resolve(self, lease_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLease:
        lease = self._leases.get(lease_id)

        if lease is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                f"No session lease is registered under lease ID {lease_id!r}."
            )

        return lease

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLeaseError(
                f"Cannot operate with an empty or blank {label}."
            )
