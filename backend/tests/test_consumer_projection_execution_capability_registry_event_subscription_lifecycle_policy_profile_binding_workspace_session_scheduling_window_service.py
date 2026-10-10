from datetime import (
    datetime,
    timedelta,
    timezone,
)

from zoneinfo import ZoneInfo

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindow as Window,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionWindowResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowService as WindowService,
)


def _at(minutes, tz=timezone.utc):
    return datetime.now(tz) + timedelta(minutes=minutes)


def _window(window_id, schedule_id, start_time, end_time, tz="UTC"):
    return Window(
        window_id=window_id,
        schedule_id=schedule_id,
        start_time=start_time,
        end_time=end_time,
        timezone=tz,
    )


class TestWorkspaceSessionSchedulingWindowService:
    def test_valid_execution_window(self):
        service = WindowService()

        service.assign("schedule-1", _window("window-1", "schedule-1", _at(-5), _at(5)))

        result = service.validate("schedule-1")

        assert isinstance(result, Result)
        assert result.executable is True
        assert result.next_window is None
        assert service.active() == ("schedule-1",)

    def test_deferred_execution(self):
        service = WindowService()

        future_start = _at(10)
        service.assign("schedule-1", _window("window-1", "schedule-1", future_start, _at(20)))

        result = service.validate("schedule-1")
        assert result.executable is False
        assert result.next_window == future_start

        deferred = service.defer("schedule-1")
        assert deferred.executable is False
        assert deferred.next_window == future_start
        assert service.active() == ()

    def test_multiple_windows(self):
        service = WindowService()

        service.assign("schedule-1", _window("window-past", "schedule-1", _at(-30), _at(-10)))
        service.assign("schedule-1", _window("window-active", "schedule-1", _at(-5), _at(5)))
        second_future_start = _at(20)
        service.assign("schedule-1", _window("window-future", "schedule-1", second_future_start, _at(30)))

        result = service.validate("schedule-1")
        assert result.executable is True

        # defer() looks strictly beyond now, so it skips the active window
        deferred = service.defer("schedule-1")
        assert deferred.executable is False
        assert deferred.next_window == second_future_start

    def test_timezone_handling(self):
        service = WindowService()

        eastern_start = _at(-5, tz=ZoneInfo("America/New_York"))
        eastern_end = _at(5, tz=ZoneInfo("America/New_York"))
        service.assign(
            "schedule-1", _window("window-1", "schedule-1", eastern_start, eastern_end, tz="America/New_York")
        )

        result = service.validate("schedule-1")

        assert result.executable is True

        with pytest.raises(Error):
            _window("window-bad-tz", "schedule-2", _at(-5), _at(5), tz="Not/AZone")

    def test_window_lookup(self):
        service = WindowService()

        assert service.next_window("schedule-1") is None

        service.assign("schedule-1", _window("window-past", "schedule-1", _at(-30), _at(-10)))
        soonest_start = _at(10)
        service.assign("schedule-1", _window("window-soon", "schedule-1", soonest_start, _at(20)))
        service.assign("schedule-1", _window("window-later", "schedule-1", _at(30), _at(40)))

        lookup = service.next_window("schedule-1")

        assert isinstance(lookup, Window)
        assert lookup.window_id == "window-soon"
        assert lookup.start_time == soonest_start

    def test_invalid_window_rejection(self):
        service = WindowService()

        with pytest.raises(Error):
            _window("window-1", "schedule-1", _at(5), _at(-5))

        with pytest.raises(Error):
            service.assign("schedule-1", "not-a-window")

        with pytest.raises(Error):
            service.assign("schedule-2", _window("window-1", "schedule-1", _at(-5), _at(5)))

        service.assign("schedule-1", _window("window-1", "schedule-1", _at(-5), _at(5)))

        with pytest.raises(Error):
            service.assign("schedule-1", _window("window-1", "schedule-1", _at(10), _at(20)))

        with pytest.raises(Error):
            service.validate("   ")

        with pytest.raises(Error):
            service.defer("   ")

        with pytest.raises(Error):
            service.next_window("   ")
