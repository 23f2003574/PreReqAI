from dataclasses import (
    dataclass,
)

from datetime import datetime

from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_calendar_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError,
)

RULES_KEYS = frozenset(
    {
        "business_days",
        "blackout_periods",
        "maintenance_windows",
    }
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendar:
    """
    Immutable, reusable definition of when a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace session schedule is allowed to execute:
    which local weekdays count as business days, and which blackout
    periods and maintenance windows are always off-limits.

    The calendar is a value object only. It performs no eligibility
    checking. Registering, assigning, and validating against
    calendars is the responsibility of a session scheduling calendar
    service.

    Attributes:
        calendar_id: The calendar's unique identifier
        name: A human-readable label for the calendar
        timezone: The IANA time zone key local weekdays are evaluated
            in
        rules: A mapping with exactly three keys:
            - "business_days": a frozenset of local weekdays (0=Monday
              through 6=Sunday) execution is allowed on
            - "blackout_periods": a tuple of (start, end)
              timezone-aware datetime pairs, each end strictly after
              its start, during which execution is always blocked
            - "maintenance_windows": a tuple of (start, end)
              timezone-aware datetime pairs, shaped like
              blackout_periods, during which execution is always
              blocked
    """

    calendar_id: str

    name: str

    timezone: str

    rules: dict

    def __post_init__(self):
        if self.calendar_id is None or not self.calendar_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                "Cannot build a session scheduling calendar with an empty or blank calendar ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                "Cannot build a session scheduling calendar with an empty or blank name."
            )

        if self.timezone is None or not self.timezone.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                "Cannot build a session scheduling calendar with an empty or blank timezone."
            )

        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                f"Cannot build a session scheduling calendar with unknown timezone {self.timezone!r}."
            ) from error

        self._validate_rules()

    def _validate_rules(self) -> None:
        if not isinstance(self.rules, dict) or set(self.rules.keys()) != RULES_KEYS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                "Cannot build a session scheduling calendar with rules that are not a dict with exactly the keys "
                "'business_days', 'blackout_periods', and 'maintenance_windows'."
            )

        business_days = self.rules["business_days"]

        if not isinstance(business_days, frozenset) or not all(
            isinstance(day, int) and not isinstance(day, bool) and 0 <= day <= 6 for day in business_days
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                "Cannot build a session scheduling calendar with business_days that is not a frozenset of "
                "weekday integers between 0 and 6."
            )

        for periods_key in ("blackout_periods", "maintenance_windows"):
            self._validate_periods(periods_key, self.rules[periods_key])

    def _validate_periods(self, key: str, periods) -> None:
        if not isinstance(periods, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                f"Cannot build a session scheduling calendar with {key} that is not a tuple of (start, end) pairs."
            )

        for period in periods:
            if (
                not isinstance(period, tuple)
                or len(period) != 2
                or not isinstance(period[0], datetime)
                or not isinstance(period[1], datetime)
                or period[0].utcoffset() is None
                or period[1].utcoffset() is None
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                    f"Cannot build a session scheduling calendar with {key} containing a non-timezone-aware "
                    "(start, end) pair."
                )

            if period[1] <= period[0]:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError(
                    f"Cannot build a session scheduling calendar with a {key} entry whose end is at or before its "
                    "start."
                )
