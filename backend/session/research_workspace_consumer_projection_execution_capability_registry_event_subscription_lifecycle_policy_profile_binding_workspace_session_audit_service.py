from datetime import datetime

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_audit_event import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent,
    VALID_SESSION_AUDIT_EVENT_TYPES,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_timeline import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionTimeline,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditService:
    """
    Maintains a complete, append-only, chronological audit log of
    every lifecycle occurrence on consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution sessions, for diagnostics, compliance,
    and replay.

    The service's responsibility is recording and retrieving audit
    events, not emitting them. It assumes the execution session
    engine, and whatever else observes a session's lifecycle, already
    knows when START, FINISH, CANCEL, and RESTORE occur; it expects a
    caller to build a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent
    and pass it to record() at the moment each one happens.

    Behavior:
    - Once recorded, an event is never modified; the log only grows,
      through record(), or shrinks, through purge()
    - timeline(), latest(), and filter() all return events in
      chronological order by timestamp, regardless of the order they
      were record()-ed in
    - purge() removes every event, across every session, older than a
      given cutoff, freeing storage under a caller-chosen retention
      policy

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._events_by_id = {}
        self._event_ids_by_session_id = {}
        self._lock = RLock()

    def record(self, event: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent:
        """
        Append a new audit event to the log.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError:
                If event is not a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent,
                or its event ID is already recorded
        """

        if not isinstance(event, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                "Cannot record an invalid session audit event: event must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent."
            )

        with self._lock:
            if event.event_id in self._events_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                    f"Event ID {event.event_id!r} is already recorded."
                )

            self._events_by_id[event.event_id] = event
            self._event_ids_by_session_id.setdefault(event.session_id, []).append(event.event_id)

            return event

    def timeline(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionTimeline:
        """
        Assemble a session's complete audit timeline, in chronological
        order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError:
                If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionTimeline(
                session_id=session_id,
                events=self._ordered_events(session_id),
            )

    def latest(self, session_id: str):
        """
        Look up a session's most recent audit event.

        Returns:
            The session's most recent ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditEvent
            by timestamp, or None if it has none

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError:
                If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            events = self._ordered_events(session_id)

            return events[-1] if events else None

    def filter(self, session_id: str, event_type: str) -> tuple:
        """
        List a session's audit events of a single type, in
        chronological order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError:
                If session_id is None or blank, or event_type is not
                one of "START", "FINISH", "CANCEL", or "RESTORE"
        """

        self._validate_id(session_id, "session ID")
        self._validate_event_type(event_type)

        with self._lock:
            return tuple(event for event in self._ordered_events(session_id) if event.event_type == event_type)

    def purge(self, before_timestamp: datetime) -> int:
        """
        Remove every audit event, across every session, older than a
        cutoff.

        Returns:
            How many events were removed

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError:
                If before_timestamp is not a datetime
        """

        if before_timestamp is None or not isinstance(before_timestamp, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                "Cannot purge session audit events with a non-datetime before_timestamp."
            )

        with self._lock:
            expired_event_ids = tuple(
                event_id for event_id, event in self._events_by_id.items() if event.timestamp < before_timestamp
            )

            for event_id in expired_event_ids:
                event = self._events_by_id.pop(event_id)

                session_event_ids = self._event_ids_by_session_id.get(event.session_id)

                if session_event_ids is not None and event_id in session_event_ids:
                    session_event_ids.remove(event_id)

            return len(expired_event_ids)

    def _ordered_events(self, session_id: str) -> tuple:
        event_ids = self._event_ids_by_session_id.get(session_id, [])

        return tuple(sorted((self._events_by_id[event_id] for event_id in event_ids), key=lambda event: event.timestamp))

    def _validate_event_type(self, event_type: str) -> None:
        if (
            event_type is None
            or not isinstance(event_type, str)
            or not event_type.strip()
            or event_type not in VALID_SESSION_AUDIT_EVENT_TYPES
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                f"Invalid session audit event_type {event_type!r}. Must be one of "
                f"{VALID_SESSION_AUDIT_EVENT_TYPES!r}."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionAuditError(
                f"Cannot operate with an empty or blank {label}."
            )
