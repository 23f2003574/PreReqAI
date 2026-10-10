import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError,
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


class TestEmptyHistoryWindow:
    """A window over an empty history is empty and has no more entries."""

    def test_empty_history_window(self):
        history = _history()

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
            history,
            0,
            5,
        )

        assert window.entries == ()
        assert window.has_more is False


class TestWindowFromBeginning:
    """A window from position 0 returns the first window_size entries."""

    def test_window_from_beginning(self):
        history = _history(0, 1, 2, 3, 4)

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
            history,
            0,
            2,
        )

        assert tuple(
            entry.sequence_number for entry in window.entries
        ) == (0, 1)
        assert window.has_more is True


class TestWindowFromMiddle:
    """A window starting mid-history returns the correct contiguous slice."""

    def test_window_from_middle(self):
        history = _history(0, 1, 2, 3, 4)

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
            history,
            2,
            2,
        )

        assert tuple(
            entry.sequence_number for entry in window.entries
        ) == (2, 3)
        assert window.has_more is True


class TestFinalPartialWindow:
    """A window that runs past the end returns only the remaining entries."""

    def test_final_partial_window(self):
        history = _history(0, 1, 2, 3, 4)

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
            history,
            3,
            5,
        )

        assert tuple(
            entry.sequence_number for entry in window.entries
        ) == (3, 4)
        assert window.has_more is False


class TestWindowLargerThanHistory:
    """A window_size larger than the entire history returns every entry."""

    def test_window_larger_than_history(self):
        history = _history(0, 1, 2)

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
            history,
            0,
            100,
        )

        assert len(window.entries) == 3
        assert window.has_more is False


class TestCorrectHasMore:
    """has_more is true exactly when entries remain beyond the window."""

    @pytest.mark.parametrize(
        "start_position,window_size,expected",
        [(0, 2, True), (2, 2, True), (4, 1, False), (0, 5, False)],
    )
    def test_correct_has_more(self, start_position, window_size, expected):
        history = _history(0, 1, 2, 3, 4)

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
            history,
            start_position,
            window_size,
        )

        assert window.has_more is expected


class TestRejectNoneHistory:
    """A None history is rejected."""

    def test_reject_none_history(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
                None,
                0,
                1,
            )


class TestRejectInvalidStartPosition:
    """A negative or out-of-bounds start position is rejected."""

    def test_reject_negative_start_position(self):
        history = _history(0, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
                history,
                -1,
                1,
            )

    def test_reject_start_position_beyond_history(self):
        history = _history(0, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
                history,
                3,
                1,
            )


class TestRejectInvalidWindowSize:
    """A non-positive window size is rejected."""

    def test_reject_zero_window_size(self):
        history = _history(0, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
                history,
                0,
                0,
            )

    def test_reject_negative_window_size(self):
        history = _history(0, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
                history,
                0,
                -1,
            )


class TestPreserveChronologicalOrdering:
    """The window preserves the exact chronological order of the history."""

    def test_preserve_chronological_ordering(self):
        history = _history(0, 1, 2, 3)

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryWindowBuilder().build(
            history,
            1,
            3,
        )

        assert tuple(
            entry.sequence_number for entry in window.entries
        ) == (1, 2, 3)
