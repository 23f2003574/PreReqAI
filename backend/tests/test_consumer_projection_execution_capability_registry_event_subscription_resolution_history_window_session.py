import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSession,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError,
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


def _window(history, start_position, window_size):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowBuilder().build(
        history,
        start_position,
        window_size,
    )


class TestBuildValidSession:
    """A well-formed input set builds a matching window session."""

    def test_build_valid_session(self):
        history = _history("first", "second", "third")
        window = _window(history, 0, 2)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
            history,
            window,
            2,
        )

        assert session.history is history
        assert session.current_window is window
        assert session.window_size == 2


class TestEmptyHistorySession:
    """A session over an empty history reports no remaining windows."""

    def test_empty_history_session(self):
        history = _history()
        window = _window(history, 0, 2)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
            history,
            window,
            2,
        )

        assert session.has_remaining_windows is False


class TestSingleWindowSession:
    """A session whose window covers the whole history has no remainder."""

    def test_single_window_session(self):
        history = _history("first", "second")
        window = _window(history, 0, 5)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
            history,
            window,
            5,
        )

        assert session.has_remaining_windows is False


class TestMultiWindowSession:
    """A session with more sessions beyond the window reports a remainder."""

    def test_multi_window_session(self):
        history = _history("first", "second", "third", "fourth")
        window = _window(history, 0, 2)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
            history,
            window,
            2,
        )

        assert session.has_remaining_windows is True


class TestCorrectHasRemainingWindows:
    """has_remaining_windows always mirrors current_window.has_more."""

    @pytest.mark.parametrize(
        "start_position,window_size,expected",
        [(0, 2, True), (2, 2, False)],
    )
    def test_correct_has_remaining_windows(
        self,
        start_position,
        window_size,
        expected,
    ):
        history = _history("first", "second", "third", "fourth")
        window = _window(history, start_position, window_size)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
            history,
            window,
            window_size,
        )

        assert session.has_remaining_windows is expected
        assert session.has_remaining_windows == window.has_more


class TestRejectNoneHistory:
    """A None history is rejected."""

    def test_reject_none_history(self):
        history = _history("first")
        window = _window(history, 0, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
                None,
                window,
                1,
            )


class TestRejectNoneCurrentWindow:
    """A None current window is rejected."""

    def test_reject_none_current_window(self):
        history = _history("first")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
                history,
                None,
                1,
            )


class TestRejectInvalidWindowSize:
    """A non-positive window size is rejected."""

    def test_reject_zero_window_size(self):
        history = _history("first")
        window = _window(history, 0, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
                history,
                window,
                0,
            )

    def test_reject_negative_window_size(self):
        history = _history("first")
        window = _window(history, 0, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
                history,
                window,
                -1,
            )


class TestRejectWindowSizeMismatch:
    """A window built with a different window size is rejected."""

    def test_reject_window_size_mismatch(self):
        history = _history("first", "second", "third")
        window = _window(history, 0, 2)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
                history,
                window,
                3,
            )


class TestImmutableAndDeterministicSession:
    """The session is a frozen dataclass and repeated builds agree."""

    def test_immutable_session(self):
        history = _history("first", "second")
        window = _window(history, 0, 1)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder().build(
            history,
            window,
            1,
        )

        assert dataclasses.is_dataclass(session)
        assert isinstance(
            session,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSession,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            session.has_remaining_windows = False

    def test_repeated_build_is_deterministic(self):
        history = _history("first", "second", "third")
        window = _window(history, 0, 2)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryWindowSessionBuilder()

        first = builder.build(history, window, 2)
        second = builder.build(history, window, 2)

        assert first == second
        assert first is not second
