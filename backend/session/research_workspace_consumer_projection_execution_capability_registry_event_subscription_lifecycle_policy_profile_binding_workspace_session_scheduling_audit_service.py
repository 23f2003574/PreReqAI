from datetime import datetime

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_audit_event import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditEvent,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_replay_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingReplayResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditService:
    """
    Maintains a complete audit trail of decisions made about consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace session schedules, and
    replays that trail deterministically for diagnostics.

    The service's responsibility is bookkeeping and replay only, not
    scheduling itself. It does NOT make scheduling decisions or emit
    audit events on its own; a caller, such as the session scheduler,
    is expected to call record() as each lifecycle event occurs.

    Behavior:
    - Audit events are append-only: record() never overwrites an
      existing event_id, and no method updates an event once recorded
    - history() lists a schedule's events newest first; replay()
      instead walks them chronologically, oldest first, to
      reconstruct the order decisions were actually made in
    - replay() is deterministic: repeated calls against the same
      recorded events always produce the same decision_trace
    - purge() is the only way retention is bounded: a caller decides,
      each time it calls purge(), how far back to keep events

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._events = {}
        self._lock = RLock()

    def record(
        self,
        event: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditEvent,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditEvent:
        """
        Record an audit event.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError:
                If event is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditEvent,
                or its event ID is already recorded
        """

        if not isinstance(event, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditEvent):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot record an invalid event: event must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditEvent."
            )

        with self._lock:
            if event.event_id in self._events:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                    f"Event ID {event.event_id!r} is already recorded."
                )

            self._events[event.event_id] = event

            return event

    def history(self, schedule_id: str) -> tuple:
        """
        List every audit event recorded for a schedule, newest first.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            return tuple(
                sorted(self._for_schedule(schedule_id), key=lambda event: event.timestamp, reverse=True)
            )

    def replay(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingReplayResult:
        """
        Deterministically replay every audit event recorded for a
        schedule, chronologically, oldest first.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            chronological = sorted(self._for_schedule(schedule_id), key=lambda event: event.timestamp)

            if not chronological:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingReplayResult(
                    schedule_id=schedule_id,
                    replayed=False,
                    decision_trace=(),
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingReplayResult(
                schedule_id=schedule_id,
                replayed=True,
                decision_trace=tuple(event.event_type for event in chronological),
            )

    def latest(
        self,
        schedule_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditEvent:
        """
        Look up the most recently recorded audit event for a
        schedule.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError:
                If schedule_id is None or blank, or no audit event is
                recorded for it
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            matching = self._for_schedule(schedule_id)

            if not matching:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                    f"No session scheduling audit event is recorded for schedule ID {schedule_id!r}."
                )

            return max(matching, key=lambda event: event.timestamp)

    def purge(self, before_timestamp: datetime) -> tuple:
        """
        Remove every recorded audit event timestamped before a given
        instant.

        Returns:
            The events that were removed, chronologically, oldest
            first

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError:
                If before_timestamp is not a timezone-aware datetime
        """

        if (
            before_timestamp is None
            or not isinstance(before_timestamp, datetime)
            or before_timestamp.utcoffset() is None
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot purge with a before_timestamp that is not a timezone-aware datetime."
            )

        with self._lock:
            removed = tuple(
                sorted(
                    (event for event in self._events.values() if event.timestamp < before_timestamp),
                    key=lambda event: event.timestamp,
                )
            )

            for event in removed:
                del self._events[event.event_id]

            return removed

    def _for_schedule(self, schedule_id: str) -> tuple:
        return tuple(event for event in self._events.values() if event.schedule_id == schedule_id)

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                f"Cannot operate with an empty or blank {label}."
            )
