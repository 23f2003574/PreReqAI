from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_heartbeat_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_heartbeat import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeat,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_heartbeat_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatService:
    """
    Monitors the liveness of consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution sessions through periodic heartbeats, so a
    caller can detect a session that has gone stale and decide
    whether it needs recovery.

    The service's responsibility is liveness tracking, not recovery
    itself. It does NOT restart, cancel, or otherwise act on a stale
    or expired session; it relies on the existing execution session
    service, given at construction time, only to confirm a session ID
    is genuinely known, and still active, before a heartbeat is
    recorded for it.

    Behavior:
    - Each session's heartbeat sequence must strictly increase;
      beat() rejects a sequence that does not exceed the last one
      recorded for that session
    - A session is healthy while its most recent heartbeat is no
      older than the configured stale timeout, and it has not been
      explicitly mark_expired()
    - A fresh beat() clears a prior mark_expired(): a heartbeat
      arriving is itself evidence the session is alive again
    - A session's full heartbeat history is kept until cleanup()
      removes it
    - cleanup() removes tracked state for any session the execution
      session service no longer reports as active, freeing it from
      further monitoring

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service, stale_timeout_seconds: float = 60.0):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known, and to check whether it is still
                active. Any object exposing `session(session_id)`,
                raising if the session is unknown and otherwise
                returning an object with a `status` attribute, is
                accepted
            stale_timeout_seconds: How long, in seconds, a session may
                go without a heartbeat before it is considered
                unhealthy

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError:
                If stale_timeout_seconds is not a positive number
        """

        if (
            stale_timeout_seconds is None
            or isinstance(stale_timeout_seconds, bool)
            or not isinstance(stale_timeout_seconds, (int, float))
            or stale_timeout_seconds <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                "Cannot build a session heartbeat service with a non-positive stale_timeout_seconds."
            )

        self._execution_session_service = execution_session_service
        self._stale_timeout = timedelta(seconds=stale_timeout_seconds)
        self._heartbeats_by_session_id = {}
        self._expired_session_ids = set()
        self._lock = RLock()

    def beat(self, session_id: str, sequence: int) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeat:
        """
        Record a heartbeat for a session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError:
                If session_id is None or blank, sequence is not a
                non-negative integer, the execution session service
                does not recognize session_id, the session is not
                active, or sequence does not exceed the session's
                last recorded sequence
        """

        self._validate_id(session_id, "session ID")
        self._validate_sequence(sequence)

        with self._lock:
            self._ensure_session_active(session_id)

            history = self._heartbeats_by_session_id.setdefault(session_id, [])

            if history and sequence <= history[-1].sequence:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                    f"Cannot record heartbeat sequence {sequence!r} for session ID {session_id!r}: it does not "
                    f"exceed the last recorded sequence {history[-1].sequence!r}."
                )

            heartbeat = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeat(
                session_id=session_id,
                sequence=sequence,
                recorded_at=datetime.now(timezone.utc),
            )

            history.append(heartbeat)
            self._expired_session_ids.discard(session_id)

            return heartbeat

    def status(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatStatus:
        """
        Assess a session's current liveness from its heartbeat
        history.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            return self._status_for(session_id)

    def stale(self) -> tuple:
        """
        List the current liveness status of every unhealthy session
        being monitored, whether unhealthy because its heartbeat has
        gone silent past the stale timeout or because it was
        mark_expired().
        """

        with self._lock:
            tracked_session_ids = set(self._heartbeats_by_session_id) | self._expired_session_ids

            return tuple(
                status
                for status in (self._status_for(session_id) for session_id in tracked_session_ids)
                if not status.healthy
            )

    def mark_expired(self, session_id: str) -> None:
        """
        Explicitly mark a session expired, so it is reported unhealthy
        by status() and stale() regardless of how recently it last
        sent a heartbeat, until its next beat().

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError:
                If session_id is None or blank, or the execution
                session service does not recognize it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            self._expired_session_ids.add(session_id)

    def cleanup(self) -> tuple:
        """
        Remove tracked heartbeat state for every session the
        execution session service no longer reports as active.

        Returns:
            The session IDs whose heartbeat state was removed
        """

        with self._lock:
            tracked_session_ids = set(self._heartbeats_by_session_id) | self._expired_session_ids

            removed = tuple(
                session_id for session_id in tracked_session_ids if not self._is_session_active(session_id)
            )

            for session_id in removed:
                self._heartbeats_by_session_id.pop(session_id, None)
                self._expired_session_ids.discard(session_id)

            return removed

    def _status_for(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatStatus:
        history = self._heartbeats_by_session_id.get(session_id, [])
        last_seen = history[-1].recorded_at if history else None

        healthy = (
            session_id not in self._expired_session_ids
            and last_seen is not None
            and (datetime.now(timezone.utc) - last_seen) <= self._stale_timeout
        )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatStatus(
            session_id=session_id,
            healthy=healthy,
            last_seen=last_seen,
        )

    def _is_session_active(self, session_id: str) -> bool:
        try:
            session = self._execution_session_service.session(session_id)
        except Exception:
            return False

        return session.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.ACTIVE

    def _ensure_session_known(self, session_id: str):
        try:
            return self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _ensure_session_active(self, session_id: str):
        session = self._ensure_session_known(session_id)

        if session.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.ACTIVE:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                f"Cannot record a heartbeat for session ID {session_id!r}: session is {session.status.value}, "
                "not active."
            )

        return session

    def _validate_sequence(self, sequence) -> None:
        if sequence is None or isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                f"Cannot record a heartbeat with sequence {sequence!r}; sequence must be a non-negative integer."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError(
                f"Cannot operate with an empty or blank {label}."
            )
