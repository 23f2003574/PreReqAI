from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendar as Calendar,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCalendarResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingCalendarService as CalendarService,
)

ALL_DAYS = frozenset(range(7))
NO_DAYS = frozenset()


def _rules(business_days=None, blackout_periods=(), maintenance_windows=()):
    return {
        "business_days": business_days if business_days is not None else ALL_DAYS,
        "blackout_periods": blackout_periods,
        "maintenance_windows": maintenance_windows,
    }


def _calendar(calendar_id, name="calendar", tz="UTC", business_days=None, blackout_periods=(), maintenance_windows=()):
    return Calendar(
        calendar_id=calendar_id,
        name=name,
        timezone=tz,
        rules=_rules(business_days, blackout_periods, maintenance_windows),
    )


def _at(minutes):
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


class TestWorkspaceSessionSchedulingCalendarService:
    def test_register_calendar(self):
        service = CalendarService()
        calendar = _calendar("calendar-1")

        registered = service.register(calendar)

        assert isinstance(registered, Calendar)
        assert service.calendars() == (calendar,)

        with pytest.raises(Error):
            service.register(calendar)

    def test_assign_calendar(self):
        service = CalendarService()
        service.register(_calendar("calendar-1"))

        service.assign("schedule-1", "calendar-1")

        with pytest.raises(Error):
            service.assign("schedule-1", "calendar-1")

        with pytest.raises(Error):
            service.assign("schedule-2", "unknown-calendar")

    def test_blackout_period_validation(self):
        service = CalendarService()
        blackout_end = _at(5)
        service.register(
            _calendar("calendar-1", business_days=ALL_DAYS, blackout_periods=((_at(-5), blackout_end),))
        )
        service.assign("schedule-1", "calendar-1")

        result = service.validate("schedule-1")

        assert isinstance(result, Result)
        assert result.executable is False
        assert result.next_valid_time is not None
        assert result.next_valid_time > blackout_end

        service.register(_calendar("calendar-2", business_days=ALL_DAYS))
        service.assign("schedule-2", "calendar-2")

        assert service.validate("schedule-2").executable is True

    def test_next_execution_calculation(self):
        service = CalendarService()
        blackout_end = _at(2)
        service.register(
            _calendar("calendar-1", business_days=ALL_DAYS, blackout_periods=((_at(-2), blackout_end),))
        )
        service.assign("schedule-1", "calendar-1")

        next_time = service.next_execution("schedule-1")

        assert next_time > blackout_end
        assert next_time <= blackout_end + timedelta(seconds=2)

        # a schedule with no calendars assigned is unrestricted
        immediate = service.next_execution("schedule-without-calendars")
        assert abs((immediate - datetime.now(timezone.utc)).total_seconds()) < 5

    def test_multiple_calendar_support(self):
        service = CalendarService()
        service.register(_calendar("calendar-permissive", business_days=ALL_DAYS))
        service.register(_calendar("calendar-restrictive", business_days=NO_DAYS))

        service.assign("schedule-1", "calendar-permissive")
        assert service.validate("schedule-1").executable is True

        service.assign("schedule-1", "calendar-restrictive")

        result = service.validate("schedule-1")
        assert result.executable is False
        assert result.next_valid_time is None

    def test_invalid_calendar_rejection(self):
        with pytest.raises(Error):
            Calendar(calendar_id="calendar-1", name="cal", timezone="UTC", rules={"business_days": ALL_DAYS})

        with pytest.raises(Error):
            Calendar(
                calendar_id="calendar-1",
                name="cal",
                timezone="UTC",
                rules=_rules(business_days={0, 1, 2}),
            )

        with pytest.raises(Error):
            Calendar(
                calendar_id="calendar-1",
                name="cal",
                timezone="UTC",
                rules=_rules(business_days=frozenset({7})),
            )

        with pytest.raises(Error):
            Calendar(
                calendar_id="calendar-1",
                name="cal",
                timezone="UTC",
                rules=_rules(blackout_periods=((_at(5), _at(-5)),)),
            )

        with pytest.raises(Error):
            _calendar("calendar-1", tz="Not/AZone")

        with pytest.raises(Error):
            _calendar("   ")

        service = CalendarService()

        with pytest.raises(Error):
            service.register("not-a-calendar")

        with pytest.raises(Error):
            service.assign("   ", "calendar-1")

        with pytest.raises(Error):
            service.validate("   ")

        with pytest.raises(Error):
            service.next_execution("   ")
