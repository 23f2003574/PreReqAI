from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from typing import Optional

from zoneinfo import ZoneInfo

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_calendar_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_calendar import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendar,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_calendar_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCalendarResult,
)

MAX_SEARCH_ITERATIONS = 3650


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarService:
    """
    Restricts consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace session
    schedules to reusable execution calendars, so a schedule only
    runs on an approved business day and outside every blackout
    period or maintenance window, deferring automatically to whatever
    valid instant comes next when it can't.

    The service's responsibility is calendar bookkeeping and
    time-based eligibility, not execution itself. It does NOT select
    or trigger a schedule for execution; a caller, such as the
    session scheduler, is expected to call validate() before
    dispatching a schedule for execution.

    Behavior:
    - Calendars are registered once, independent of any schedule, and
      may then be assigned to any number of schedules; a schedule may
      likewise have any number of calendars assigned to it
    - A schedule with no calendars assigned is unrestricted: it is
      always executable
    - A schedule with calendars assigned is executable only when
      every one of them currently allows it: the instant falls on one
      of that calendar's business days, in its own time zone, and
      outside all of its blackout periods and maintenance windows
    - next_execution() always returns a concrete instant: the current
      one if already valid, otherwise the next instant, strictly
      later, at which every assigned calendar would allow it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._calendars = {}
        self._calendar_order = []
        self._calendar_ids_by_schedule_id = {}
        self._lock = RLock()

    def register(
        self,
        calendar: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendar,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendar:
        """
        Register a reusable calendar.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError:
                If calendar is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendar,
                or its calendar ID is already registered
        """

        if not isinstance(calendar, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendar):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                "Cannot register an invalid calendar: calendar must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendar."
            )

        with self._lock:
            if calendar.calendar_id in self._calendars:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                    f"Calendar ID {calendar.calendar_id!r} is already registered."
                )

            self._calendars[calendar.calendar_id] = calendar
            self._calendar_order.append(calendar.calendar_id)

            return calendar

    def assign(self, schedule_id: str, calendar_id: str) -> None:
        """
        Assign a registered calendar to a schedule.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError:
                If schedule_id or calendar_id is None or blank, no
                calendar is registered under calendar_id, or it is
                already assigned to schedule_id
        """

        self._validate_id(schedule_id, "schedule ID")
        self._validate_id(calendar_id, "calendar ID")

        with self._lock:
            self._resolve_calendar(calendar_id)

            assigned = self._calendar_ids_by_schedule_id.setdefault(schedule_id, [])

            if calendar_id in assigned:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                    f"Calendar ID {calendar_id!r} is already assigned to schedule ID {schedule_id!r}."
                )

            assigned.append(calendar_id)

    def validate(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCalendarResult:
        """
        Check whether a schedule currently satisfies every calendar
        assigned to it.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            now = datetime.now(timezone.utc)
            calendars = self._assigned_calendars(schedule_id)

            if self._is_valid(calendars, now):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCalendarResult(
                    executable=True,
                    next_valid_time=None,
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCalendarResult(
                executable=False,
                next_valid_time=self._next_valid_time(calendars, now),
            )

    def next_execution(self, schedule_id: str) -> Optional[datetime]:
        """
        Compute the next instant at which a schedule would satisfy
        every calendar assigned to it: the current instant if already
        valid, otherwise the next one, strictly later.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            now = datetime.now(timezone.utc)
            calendars = self._assigned_calendars(schedule_id)

            if self._is_valid(calendars, now):
                return now

            return self._next_valid_time(calendars, now)

    def calendars(self) -> tuple:
        """
        List every registered calendar, in registration order.
        """

        with self._lock:
            return tuple(self._calendars[calendar_id] for calendar_id in self._calendar_order)

    def _assigned_calendars(self, schedule_id: str) -> tuple:
        return tuple(
            self._calendars[calendar_id]
            for calendar_id in self._calendar_ids_by_schedule_id.get(schedule_id, ())
        )

    def _is_valid(self, calendars: tuple, instant: datetime) -> bool:
        return all(self._calendar_allows(calendar, instant) for calendar in calendars)

    def _calendar_allows(
        self,
        calendar: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendar,
        instant: datetime,
    ) -> bool:
        local_weekday = instant.astimezone(ZoneInfo(calendar.timezone)).weekday()

        if local_weekday not in calendar.rules["business_days"]:
            return False

        for start, end in calendar.rules["blackout_periods"] + calendar.rules["maintenance_windows"]:
            if start <= instant <= end:
                return False

        return True

    def _next_valid_time(self, calendars: tuple, after: datetime) -> Optional[datetime]:
        if not calendars:
            return after

        candidate = after + timedelta(seconds=1)

        for _ in range(MAX_SEARCH_ITERATIONS):
            if self._is_valid(calendars, candidate):
                return candidate

            resume_points = []

            for calendar in calendars:
                local_weekday = candidate.astimezone(ZoneInfo(calendar.timezone)).weekday()

                if local_weekday not in calendar.rules["business_days"]:
                    resume_points.append(candidate + timedelta(days=1))

                for start, end in calendar.rules["blackout_periods"] + calendar.rules["maintenance_windows"]:
                    if start <= candidate <= end:
                        resume_points.append(end + timedelta(seconds=1))

            if not resume_points:
                return None

            candidate = min(resume_points)

        return None

    def _resolve_calendar(
        self,
        calendar_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendar:
        calendar = self._calendars.get(calendar_id)

        if calendar is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                f"No session scheduling calendar is registered under calendar ID {calendar_id!r}."
            )

        return calendar

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                f"Cannot operate with an empty or blank {label}."
            )
