import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryNavigator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryNavigatorError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder,
)


class _Subscriber(
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber
):
    def handle(self, event):
        return None


def _subscription(name="subscription"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder().build(
        _Subscriber(),
        name,
    )


_STATE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState


def _execution_result(subscription):
    previous_lifecycle = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
        subscription,
        _STATE.REGISTERED,
    )

    transition = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
        subscription,
        _STATE.REGISTERED,
        _STATE.ACTIVE,
    )

    resulting_lifecycle = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder().build(
        subscription,
        _STATE.ACTIVE,
    )

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionResultBuilder().build(
        previous_lifecycle,
        transition,
        resulting_lifecycle,
    )


def _entry(sequence_number):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder().build(
        sequence_number,
        _execution_result(_subscription()),
    )


def _history(*sequence_numbers):
    entries = tuple(_entry(number) for number in sequence_numbers)

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBuilder().build(
        entries
    )


def _navigator():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryNavigator(
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder()
    )


class TestFirstCursorOnPopulatedHistory:
    """first() builds a cursor at position 0 for a non-empty history."""

    def test_first_cursor_on_populated_history(self):
        history = _history(0, 1, 2)

        cursor = _navigator().first(history)

        assert cursor.position == 0
        assert cursor.has_next is True


class TestFirstCursorOnEmptyHistory:
    """first() builds a cursor at position 0 for an empty history."""

    def test_first_cursor_on_empty_history(self):
        history = _history()

        cursor = _navigator().first(history)

        assert cursor.position == 0
        assert cursor.has_next is False


class TestLastCursorOnPopulatedHistory:
    """last() builds a cursor at the final valid position."""

    def test_last_cursor_on_populated_history(self):
        history = _history(0, 1, 2)

        cursor = _navigator().last(history)

        assert cursor.position == 2
        assert cursor.has_next is True


class TestLastCursorOnEmptyHistory:
    """last() builds a cursor at position 0 for an empty history."""

    def test_last_cursor_on_empty_history(self):
        history = _history()

        cursor = _navigator().last(history)

        assert cursor.position == 0
        assert cursor.has_next is False


class TestNextAdvancesCorrectly:
    """next() moves the cursor forward by one position."""

    def test_next_advances_correctly(self):
        navigator = _navigator()
        history = _history(0, 1, 2)
        cursor = navigator.first(history)

        advanced = navigator.next(history, cursor)

        assert advanced.position == 1


class TestNextClampsAtEnd:
    """next() at the end of the history returns the identical cursor."""

    def test_next_clamps_at_end(self):
        navigator = _navigator()
        history = _history(0, 1)
        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
            history,
            2,
        )

        result = navigator.next(history, cursor)

        assert result is cursor


class TestPreviousMovesCorrectly:
    """previous() moves the cursor back by one position."""

    def test_previous_moves_correctly(self):
        navigator = _navigator()
        history = _history(0, 1, 2)
        cursor = navigator.last(history)

        moved = navigator.previous(history, cursor)

        assert moved.position == 1


class TestPreviousClampsAtZero:
    """previous() at position 0 returns the identical cursor."""

    def test_previous_clamps_at_zero(self):
        navigator = _navigator()
        history = _history(0, 1)
        cursor = navigator.first(history)

        result = navigator.previous(history, cursor)

        assert result is cursor


class TestRejectInvalidInputs:
    """None history and None cursor are rejected across all methods."""

    def test_reject_none_history_first(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryNavigatorError
        ):
            _navigator().first(None)

    def test_reject_none_history_last(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryNavigatorError
        ):
            _navigator().last(None)

    def test_reject_none_history_next(self):
        navigator = _navigator()
        history = _history(0)
        cursor = navigator.first(history)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryNavigatorError
        ):
            navigator.next(None, cursor)

    def test_reject_none_history_previous(self):
        navigator = _navigator()
        history = _history(0)
        cursor = navigator.first(history)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryNavigatorError
        ):
            navigator.previous(None, cursor)

    def test_reject_none_cursor_next(self):
        navigator = _navigator()
        history = _history(0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryNavigatorError
        ):
            navigator.next(history, None)

    def test_reject_none_cursor_previous(self):
        navigator = _navigator()
        history = _history(0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryNavigatorError
        ):
            navigator.previous(history, None)


class _CountingCursorBuilder:
    def __init__(self):
        self.calls = 0

    def build(self, history, position):
        self.calls += 1

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
            history,
            position,
        )


class TestCursorBuilderInvokedForEveryReturnedCursor:
    """The injected cursor builder is invoked for first, last, next, and previous."""

    def test_cursor_builder_invoked_for_every_returned_cursor(self):
        cursor_builder = _CountingCursorBuilder()

        navigator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryNavigator(
            cursor_builder
        )

        history = _history(0, 1, 2)

        first_cursor = navigator.first(history)
        assert cursor_builder.calls == 1

        last_cursor = navigator.last(history)
        assert cursor_builder.calls == 2

        navigator.next(history, first_cursor)
        assert cursor_builder.calls == 3

        navigator.previous(history, last_cursor)
        assert cursor_builder.calls == 4
