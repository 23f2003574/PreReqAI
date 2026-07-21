import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReadResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReaderError,
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


def _cursor(history, position):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryCursorBuilder().build(
        history,
        position,
    )


class TestReadFirstSession:
    """Reading at position 0 returns the first session."""

    def test_read_first_session(self):
        history = _history("first", "second", "third")
        cursor = _cursor(history, 0)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.session is history.sessions[0]
        assert result.reached_end is False


class TestReadMiddleSession:
    """Reading in the middle returns the session at that position."""

    def test_read_middle_session(self):
        history = _history("first", "second", "third")
        cursor = _cursor(history, 1)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.session is history.sessions[1]
        assert result.reached_end is False


class TestReadFinalSession:
    """Reading at the last valid position returns the last session."""

    def test_read_final_session(self):
        history = _history("first", "second", "third")
        cursor = _cursor(history, 2)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.session is history.sessions[2]
        assert result.reached_end is False


class TestReadEmptyHistory:
    """Reading an empty history at position 0 reaches the end immediately."""

    def test_read_empty_history(self):
        history = _history()
        cursor = _cursor(history, 0)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.session is None
        assert result.reached_end is True


class TestEndOfHistoryReturnsNone:
    """A cursor with no next session yields a None session."""

    def test_end_of_history_returns_none(self):
        history = _history("first", "second")
        cursor = _cursor(history, 2)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.session is None
        assert result.reached_end is True


class TestReturnedCursorUnchanged:
    """The reader returns the exact same cursor it was given."""

    def test_returned_cursor_unchanged(self):
        history = _history("first", "second")
        cursor = _cursor(history, 1)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.cursor is cursor


class TestRejectNoneHistory:
    """A None history is rejected."""

    def test_reject_none_history(self):
        history = _history("first")
        cursor = _cursor(history, 0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReaderError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader().read(
                None,
                cursor,
            )


class TestRejectNoneCursor:
    """A None cursor is rejected."""

    def test_reject_none_cursor(self):
        history = _history("first")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReaderError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader().read(
                history,
                None,
            )


class TestRejectInvalidCursorPosition:
    """A cursor built against a different, shorter history is rejected."""

    def test_reject_invalid_cursor_position(self):
        long_history = _history("first", "second", "third")
        short_history = _history("first")

        cursor = _cursor(long_history, 2)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReaderError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader().read(
                short_history,
                cursor,
            )


class TestDeterministicOutput:
    """Reading the same history and cursor twice agrees, and yields the result type."""

    def test_deterministic_output(self):
        history = _history("first", "second")
        cursor = _cursor(history, 0)

        reader = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReader()

        first = reader.read(history, cursor)
        second = reader.read(history, cursor)

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionResolutionHistoryReadResult,
        )
