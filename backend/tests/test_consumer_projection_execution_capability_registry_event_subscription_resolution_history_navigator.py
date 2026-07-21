import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryNavigator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryNavigatorError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder,
)


class _Subscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    def handle(self, event):
        return None


class _Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"_Event({self.name!r})"


def _session(name):
    event = _Event(name)

    subscription = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
        _Subscriber(),
        f"subscription-{name}",
    )

    resolution = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder().build(
        event,
        (subscription,),
    )

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionSessionBuilder().build(
        event,
        resolution,
    )


def _history(*names):
    sessions = tuple(_session(name) for name in names)

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBuilder().build(
        sessions
    )


def _navigator():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryNavigator(
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorBuilder()
    )


class TestNavigateToFirstCursor:
    """first() builds a cursor at position 0."""

    def test_navigate_to_first_cursor(self):
        history = _history("first", "second", "third")

        cursor = _navigator().first(history)

        assert cursor.position == 0
        assert cursor.has_next is True


class TestNavigateToLastCursor:
    """last() builds a cursor at the final valid position."""

    def test_navigate_to_last_cursor(self):
        history = _history("first", "second", "third")

        cursor = _navigator().last(history)

        assert cursor.position == 2
        assert cursor.has_next is True


class TestAdvanceToNextCursor:
    """next() moves the cursor forward by one position."""

    def test_advance_to_next_cursor(self):
        navigator = _navigator()
        history = _history("first", "second", "third")
        cursor = navigator.first(history)

        advanced = navigator.next(history, cursor)

        assert advanced.position == 1


class TestMoveToPreviousCursor:
    """previous() moves the cursor back by one position."""

    def test_move_to_previous_cursor(self):
        navigator = _navigator()
        history = _history("first", "second", "third")
        cursor = navigator.last(history)

        moved = navigator.previous(history, cursor)

        assert moved.position == 1


class TestEmptyHistory:
    """first() and last() both land on position 0 for an empty history."""

    def test_empty_history(self):
        navigator = _navigator()
        history = _history()

        first_cursor = navigator.first(history)
        last_cursor = navigator.last(history)

        assert first_cursor.position == 0
        assert last_cursor.position == 0
        assert first_cursor.has_next is False
        assert last_cursor.has_next is False


class TestNextAtEndReturnsSameCursor:
    """next() at the end of the history returns the identical cursor."""

    def test_next_at_end_returns_same_cursor(self):
        navigator = _navigator()
        history = _history("first", "second")
        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorBuilder().build(
            history,
            2,
        )

        result = navigator.next(history, cursor)

        assert result is cursor


class TestPreviousAtBeginningReturnsSameCursor:
    """previous() at position 0 returns the identical cursor."""

    def test_previous_at_beginning_returns_same_cursor(self):
        navigator = _navigator()
        history = _history("first", "second")
        cursor = navigator.first(history)

        result = navigator.previous(history, cursor)

        assert result is cursor


class TestRejectNoneHistory:
    """A None history is rejected by every navigation method."""

    def test_reject_none_history_first(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryNavigatorError
        ):
            _navigator().first(None)

    def test_reject_none_history_last(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryNavigatorError
        ):
            _navigator().last(None)

    def test_reject_none_history_next(self):
        navigator = _navigator()
        history = _history("first")
        cursor = navigator.first(history)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryNavigatorError
        ):
            navigator.next(None, cursor)

    def test_reject_none_history_previous(self):
        navigator = _navigator()
        history = _history("first")
        cursor = navigator.first(history)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryNavigatorError
        ):
            navigator.previous(None, cursor)


class TestRejectNoneCursor:
    """A None cursor is rejected by next() and previous()."""

    def test_reject_none_cursor_next(self):
        navigator = _navigator()
        history = _history("first")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryNavigatorError
        ):
            navigator.next(history, None)

    def test_reject_none_cursor_previous(self):
        navigator = _navigator()
        history = _history("first")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryNavigatorError
        ):
            navigator.previous(history, None)


class TestDeterministicNavigation:
    """Repeating the same navigation call twice agrees."""

    def test_deterministic_navigation(self):
        navigator = _navigator()
        history = _history("first", "second", "third")
        cursor = navigator.first(history)

        first_next = navigator.next(history, cursor)
        second_next = navigator.next(history, cursor)

        assert first_next == second_next
        assert first_next is not second_next


class TestNavigatorHoldsOnlyItsDependency:
    """The navigator stores only the cursor builder it was given."""

    def test_navigator_holds_only_its_dependency(self):
        cursor_builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorBuilder()

        navigator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryNavigator(
            cursor_builder
        )

        assert navigator.__dict__ == {
            "_cursor_builder": cursor_builder,
        }
