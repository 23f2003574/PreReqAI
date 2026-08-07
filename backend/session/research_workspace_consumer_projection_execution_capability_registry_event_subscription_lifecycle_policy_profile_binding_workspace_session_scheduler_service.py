from dataclasses import replace

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedule,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulerService:
    """
    Schedules consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    sessions for future or recurring execution using reusable
    schedules, so a session can be triggered later, or repeatedly,
    without a caller having to re-request it each time.

    The service's responsibility is schedule bookkeeping only. It
    does NOT trigger a session's execution itself; it relies on the
    existing execution session service, given at construction time,
    only to confirm a session ID is genuinely known before a schedule
    is created on its behalf. A caller is expected to trigger a
    session's execution elsewhere, then call reschedule() or cancel()
    to keep the schedule current.

    Behavior:
    - At most one schedule may exist per session at a time; schedule()
      rejects a session that already has one, until it is cancelled
    - reschedule() advances a recurring schedule's trigger_at by its
      recurrence; it cannot advance a schedule with no recurrence
    - cancel() removes a schedule entirely, freeing its session for a
      new schedule() call; a cancelled schedule never executes again
    - next() and pending() only ever consider enabled schedules,
      ordered by trigger_at, soonest first

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known before a schedule is created on
                its behalf. Any object exposing `session(session_id)`,
                raising if the session is unknown, is accepted
        """

        self._execution_session_service = execution_session_service
        self._schedules = {}
        self._active_schedule_id_by_session_id = {}
        self._lock = RLock()

    def schedule(
        self,
        session_id: str,
        schedule: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedule,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedule:
        """
        Create a schedule on behalf of a session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError:
                If session_id is None or blank, schedule is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedule
                belonging to session_id, the execution session service
                does not recognize session_id, the session already has
                a schedule, or the schedule ID is already registered
        """

        self._validate_id(session_id, "session ID")

        if not isinstance(schedule, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedule):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                "Cannot create an invalid schedule: schedule must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedule."
            )

        if schedule.session_id != session_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                f"Cannot create a schedule for session ID {schedule.session_id!r} on behalf of session ID "
                f"{session_id!r}."
            )

        with self._lock:
            self._ensure_session_known(session_id)

            if session_id in self._active_schedule_id_by_session_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                    f"Cannot create a schedule for session ID {session_id!r}: it already has an active schedule."
                )

            if schedule.schedule_id in self._schedules:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                    f"Schedule ID {schedule.schedule_id!r} is already registered."
                )

            self._schedules[schedule.schedule_id] = schedule
            self._active_schedule_id_by_session_id[session_id] = schedule.schedule_id

            return schedule

    def reschedule(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleResult:
        """
        Advance a recurring schedule to its next due run.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError:
                If schedule_id is None or blank, no schedule is
                registered under it, or the schedule has no
                recurrence
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            existing = self._resolve(schedule_id)

            if existing.recurrence is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                    f"Cannot reschedule schedule ID {schedule_id!r}: it has no recurrence."
                )

            next_trigger_at = existing.trigger_at + existing.recurrence

            self._schedules[schedule_id] = replace(existing, trigger_at=next_trigger_at)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleResult(
                schedule_id=schedule_id,
                next_execution=next_trigger_at,
            )

    def cancel(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleResult:
        """
        Cancel a schedule, freeing its session immediately.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError:
                If schedule_id is None or blank, or no schedule is
                registered under it
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            self._resolve(schedule_id)

            self._forget(schedule_id)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleResult(
                schedule_id=schedule_id,
                next_execution=None,
            )

    def next(self):
        """
        Look up the enabled schedule due to run soonest.

        Returns:
            The
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedule
            with the earliest trigger_at among enabled schedules, or
            None if none are enabled
        """

        with self._lock:
            enabled = tuple(schedule for schedule in self._schedules.values() if schedule.enabled)

            if not enabled:
                return None

            return min(enabled, key=lambda schedule: schedule.trigger_at)

    def pending(self) -> tuple:
        """
        List every enabled schedule, ordered by trigger_at, soonest
        first.
        """

        with self._lock:
            enabled = tuple(schedule for schedule in self._schedules.values() if schedule.enabled)

            return tuple(sorted(enabled, key=lambda schedule: schedule.trigger_at))

    def _forget(self, schedule_id: str) -> None:
        schedule = self._schedules.pop(schedule_id, None)

        if schedule is None:
            return

        if self._active_schedule_id_by_session_id.get(schedule.session_id) == schedule_id:
            del self._active_schedule_id_by_session_id[schedule.session_id]

    def _ensure_session_known(self, session_id: str) -> None:
        try:
            self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _resolve(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedule:
        schedule = self._schedules.get(schedule_id)

        if schedule is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                f"No session schedule is registered under schedule ID {schedule_id!r}."
            )

        return schedule

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                f"Cannot operate with an empty or blank {label}."
            )
