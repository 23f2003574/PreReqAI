from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionSchedulingWindow,
    ExecutionSchedulingWindowError as Error,
    ExecutionSchedulingWindowService,
)

NOON = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def _build():
    return ExecutionSchedulingWindowService()


class TestExecutionSchedulingWindowService:
    def test_create_and_disable(self):
        service = _build()

        window = service.create("scope-1", NOON, NOON + timedelta(hours=1))

        assert isinstance(window, ExecutionSchedulingWindow)
        assert window.scope_id == "scope-1"
        assert window.enabled is True

        disabled = service.disable(window.window_id)

        assert disabled.enabled is False
        assert service.active("scope-1", NOON) is False

    def test_disabling_unknown_window_is_an_error(self):
        service = _build()

        with pytest.raises(Error):
            service.disable("does-not-exist")

    def test_disabling_already_disabled_window_is_an_error(self):
        service = _build()
        window = service.create("scope-1", NOON, NOON + timedelta(hours=1))
        service.disable(window.window_id)

        with pytest.raises(Error):
            service.disable(window.window_id)

    def test_active_window(self):
        service = _build()
        service.create("scope-1", NOON, NOON + timedelta(hours=1))

        assert service.active("scope-1", NOON) is True
        assert service.active("scope-1", NOON + timedelta(minutes=30)) is True

    def test_outside_window_rejection(self):
        service = _build()
        service.create("scope-1", NOON, NOON + timedelta(hours=1))

        assert service.active("scope-1", NOON - timedelta(minutes=1)) is False
        assert service.active("scope-1", NOON + timedelta(hours=1)) is False

    def test_disabled_window_is_never_active(self):
        service = _build()
        window = service.create("scope-1", NOON, NOON + timedelta(hours=1))
        service.disable(window.window_id)

        assert service.active("scope-1", NOON + timedelta(minutes=30)) is False

    def test_next_window_lookup(self):
        service = _build()
        later = service.create("scope-1", NOON + timedelta(hours=2), NOON + timedelta(hours=3))
        service.create("scope-1", NOON + timedelta(hours=5), NOON + timedelta(hours=6))

        found = service.next("scope-1", NOON)

        assert found.window_id == later.window_id

    def test_next_window_returns_currently_active_window(self):
        service = _build()
        current = service.create("scope-1", NOON, NOON + timedelta(hours=1))
        service.create("scope-1", NOON + timedelta(hours=5), NOON + timedelta(hours=6))

        found = service.next("scope-1", NOON + timedelta(minutes=30))

        assert found.window_id == current.window_id

    def test_next_window_returns_none_when_nothing_upcoming(self):
        service = _build()
        service.create("scope-1", NOON, NOON + timedelta(hours=1))

        assert service.next("scope-1", NOON + timedelta(hours=2)) is None

    def test_overlap_handling(self):
        service = _build()
        first = service.create("scope-1", NOON, NOON + timedelta(hours=2))
        second = service.create("scope-1", NOON + timedelta(hours=1), NOON + timedelta(hours=3))

        assert service.active("scope-1", NOON + timedelta(hours=1, minutes=30)) is True

        found_first = service.next("scope-1", NOON)
        found_second = service.next("scope-1", NOON)

        assert found_first.window_id == first.window_id
        assert found_second.window_id == first.window_id

    def test_invalid_time_range_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.create("scope-1", NOON, NOON)

        with pytest.raises(Error):
            service.create("scope-1", NOON + timedelta(hours=1), NOON)

    def test_scope_isolation(self):
        service = _build()
        service.create("scope-1", NOON, NOON + timedelta(hours=1))

        assert service.active("scope-2", NOON) is False
