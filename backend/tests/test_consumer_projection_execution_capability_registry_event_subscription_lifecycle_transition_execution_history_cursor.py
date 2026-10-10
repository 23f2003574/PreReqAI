import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder,
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


class TestEmptyHistoryCursor:
    """A cursor over an empty history at position 0 has no next entry."""

    def test_empty_history_cursor(self):
        history = _history()

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
            history,
            0,
        )

        assert cursor.position == 0
        assert cursor.remaining_entries == 0
        assert cursor.has_next is False


class TestCursorAtBeginning:
    """A cursor at position 0 of a non-empty history reports remaining entries."""

    def test_cursor_at_beginning(self):
        history = _history(0, 1, 2)

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
            history,
            0,
        )

        assert cursor.remaining_entries == 3
        assert cursor.has_next is True


class TestCursorInMiddle:
    """A cursor mid-history reports the exact position and remaining count."""

    def test_cursor_in_middle(self):
        history = _history(0, 1, 2)

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
            history,
            1,
        )

        assert cursor.position == 1
        assert cursor.remaining_entries == 2
        assert cursor.has_next is True


class TestCursorAtEnd:
    """A cursor at the final position has no next entry."""

    def test_cursor_at_end(self):
        history = _history(0, 1, 2)

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
            history,
            3,
        )

        assert cursor.position == 3
        assert cursor.remaining_entries == 0
        assert cursor.has_next is False


class TestCorrectRemainingEntryCount:
    """remaining_entries always equals entry_count minus position."""

    @pytest.mark.parametrize("position", [0, 1, 2, 4])
    def test_correct_remaining_entry_count(self, position):
        history = _history(0, 1, 2, 3)

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
            history,
            position,
        )

        assert cursor.remaining_entries == history.entry_count - position


class TestCorrectHasNext:
    """has_next is true exactly when position is before entry_count."""

    @pytest.mark.parametrize(
        "position,expected",
        [(0, True), (1, True), (2, False)],
    )
    def test_correct_has_next(self, position, expected):
        history = _history(0, 1)

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
            history,
            position,
        )

        assert cursor.has_next is expected


class TestRejectNegativePosition:
    """A negative position is rejected."""

    def test_reject_negative_position(self):
        history = _history(0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
                history,
                -1,
            )


class TestRejectPositionBeyondHistory:
    """A position beyond the history's entry count is rejected."""

    def test_reject_position_beyond_history(self):
        history = _history(0, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
                history,
                3,
            )


class TestImmutableConstruction:
    """A built cursor cannot have its fields reassigned."""

    def test_immutable_construction(self):
        history = _history(0)

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
            history,
            0,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            cursor.position = 1


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct cursors."""

    def test_deterministic_construction(self):
        history = _history(0, 1)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder()

        first = builder.build(history, 1)
        second = builder.build(history, 1)

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursor,
        )
