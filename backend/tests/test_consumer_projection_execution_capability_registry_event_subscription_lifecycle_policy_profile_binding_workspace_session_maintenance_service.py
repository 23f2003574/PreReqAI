import time

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceWindow as Window,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceService as MaintenanceService,
)


def _at(offset):
    return datetime.now(timezone.utc) + timedelta(seconds=offset)


def _window(window_id, starts_at, ends_at, scope="global"):
    return Window(window_id=window_id, starts_at=starts_at, ends_at=ends_at, scope=scope)


class TestWorkspaceSessionMaintenanceService:
    def test_enable_maintenance(self):
        service = MaintenanceService()
        window = _window("window-1", _at(-300), _at(300))

        enabled = service.enable(window)

        assert isinstance(enabled, Window)
        assert service.active() == (window,)

        with pytest.raises(Error):
            service.enable(window)

        service.disable("window-1")
        assert service.active() == ()

        with pytest.raises(Error):
            service.disable("window-1")

    def test_suspend_scheduling(self):
        service = MaintenanceService()
        service.enable(_window("window-1", _at(-300), _at(300)))

        result = service.suspend()

        assert isinstance(result, Result)
        assert result.suspended is True
        assert result.resumed is False

        # suspend() stays consistent on repeated calls while still active
        assert service.suspend().suspended is True

    def test_resume_scheduling(self):
        service = MaintenanceService()
        service.enable(_window("window-1", _at(-1), _at(0.1)))

        assert service.suspend().suspended is True

        # still inside the window: not yet eligible to resume
        still_paused = service.resume()
        assert still_paused.suspended is True
        assert still_paused.resumed is False

        time.sleep(0.2)

        resumed = service.resume()
        assert resumed.suspended is False
        assert resumed.resumed is True

        # already resumed: a further call reports steady state, not another resumption
        steady = service.resume()
        assert steady.suspended is False
        assert steady.resumed is False

    def test_queued_session_preservation(self):
        service = MaintenanceService()
        service.enable(_window("window-1", _at(-300), _at(300)))

        service.suspend()

        # new work being tracked elsewhere (represented here by another
        # window being enabled) is not discarded or altered by suspending
        service.enable(_window("window-2", _at(-300), _at(300), scope="worker-1"))

        assert {window.window_id for window in service.active()} == {"window-1", "window-2"}
        assert service.suspend().suspended is True

    def test_scoped_maintenance(self):
        service = MaintenanceService()
        service.enable(_window("window-scoped", _at(-300), _at(300), scope="worker-1"))

        assert [window.window_id for window in service.active()] == ["window-scoped"]

        # a non-global scope is visible but does not pause dispatch on its own
        result = service.suspend()
        assert result.suspended is False

    def test_expired_window_cleanup(self):
        service = MaintenanceService()
        service.enable(_window("window-1", _at(-600), _at(-300)))

        assert service.active() == ()

        result = service.suspend()
        assert result.suspended is False
