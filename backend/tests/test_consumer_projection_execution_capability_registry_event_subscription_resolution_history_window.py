import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError,
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


class TestEmptyHistoryWindow:
    """A window over an empty history has no sessions and no more."""

    def test_empty_history_window(self):
        history = _history()

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
            history,
            0,
            2,
        )

        assert window.sessions == ()
        assert window.has_more is False


class TestWindowFromBeginning:
    """A window at the beginning returns the first window_size sessions."""

    def test_window_from_beginning(self):
        history = _history("first", "second", "third", "fourth")

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
            history,
            0,
            2,
        )

        assert window.sessions == history.sessions[0:2]
        assert window.has_more is True


class TestMiddleWindow:
    """A window starting mid-history returns the correct slice."""

    def test_middle_window(self):
        history = _history("first", "second", "third", "fourth")

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
            history,
            1,
            2,
        )

        assert window.sessions == history.sessions[1:3]
        assert window.has_more is True


class TestFinalPartialWindow:
    """A window that reaches the end returns fewer sessions than requested."""

    def test_final_partial_window(self):
        history = _history("first", "second", "third")

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
            history,
            2,
            2,
        )

        assert window.sessions == history.sessions[2:3]
        assert window.has_more is False


class TestWindowLargerThanHistory:
    """A window size larger than the history returns every session."""

    def test_window_larger_than_history(self):
        history = _history("first", "second")

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
            history,
            0,
            10,
        )

        assert window.sessions == history.sessions
        assert window.has_more is False


class TestCorrectHasMore:
    """has_more is true exactly when sessions remain beyond the window."""

    @pytest.mark.parametrize(
        "start_position,window_size,expected",
        [(0, 2, True), (2, 2, True), (4, 2, False)],
    )
    def test_correct_has_more(self, start_position, window_size, expected):
        history = _history("a", "b", "c", "d", "e", "f")

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
            history,
            start_position,
            window_size,
        )

        assert window.has_more is expected


class TestRejectInvalidStartPosition:
    """A negative or out-of-range start position is rejected."""

    def test_reject_negative_start_position(self):
        history = _history("first")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
                history,
                -1,
                1,
            )

    def test_reject_out_of_range_start_position(self):
        history = _history("first", "second")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
                history,
                3,
                1,
            )


class TestRejectInvalidWindowSize:
    """A non-positive window size is rejected."""

    def test_reject_zero_window_size(self):
        history = _history("first")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
                history,
                0,
                0,
            )

    def test_reject_negative_window_size(self):
        history = _history("first")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
                history,
                0,
                -1,
            )


class TestPreserveSessionOrdering:
    """Sessions within the window retain their chronological order."""

    def test_preserve_session_ordering(self):
        history = _history("first", "second", "third", "fourth", "fifth")

        window = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
            history,
            1,
            3,
        )

        assert window.sessions == (
            history.sessions[1],
            history.sessions[2],
            history.sessions[3],
        )


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct windows."""

    def test_deterministic_construction(self):
        history = _history("first", "second", "third")

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder()

        first = builder.build(history, 0, 2)
        second = builder.build(history, 0, 2)

        assert first == second
        assert first is not second
