import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder,
)


class _Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"_Event({self.name!r})"


def _session(name):
    event = _Event(name)

    dispatch_result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
        event,
        subscriber_count=1,
        successful_dispatch_count=1,
    )

    publication_result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
        event,
        resolved_subscriber_count=1,
        dispatch_result=dispatch_result,
    )

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
        event,
        publication_result,
    )


def _history(*names):
    sessions = tuple(_session(name) for name in names)

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
        sessions
    )


class TestCursorAtBeginning:
    """A cursor built at position 0 has the full history ahead of it."""

    def test_cursor_at_beginning(self):
        history = _history("first", "second", "third")

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
            history,
            0,
        )

        assert cursor.position == 0
        assert cursor.remaining_sessions == 3
        assert cursor.has_next is True


class TestCursorInMiddle:
    """A cursor built partway through the history reflects that position."""

    def test_cursor_in_middle(self):
        history = _history("first", "second", "third")

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
            history,
            1,
        )

        assert cursor.position == 1
        assert cursor.remaining_sessions == 2
        assert cursor.has_next is True


class TestCursorAtEnd:
    """A cursor built at the final position has nothing left ahead."""

    def test_cursor_at_end(self):
        history = _history("first", "second", "third")

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
            history,
            3,
        )

        assert cursor.position == 3
        assert cursor.remaining_sessions == 0
        assert cursor.has_next is False


class TestEmptyHistory:
    """A cursor over an empty history is immediately at the end."""

    def test_empty_history(self):
        history = _history()

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
            history,
            0,
        )

        assert cursor.position == 0
        assert cursor.remaining_sessions == 0
        assert cursor.has_next is False


class TestCorrectRemainingSessions:
    """remaining_sessions always equals session_count - position."""

    @pytest.mark.parametrize("position", [0, 1, 2, 3, 4])
    def test_correct_remaining_sessions(self, position):
        history = _history("a", "b", "c", "d")

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
            history,
            position,
        )

        assert cursor.remaining_sessions == history.session_count - position


class TestCorrectHasNext:
    """has_next is true exactly when position hasn't reached the end."""

    @pytest.mark.parametrize(
        "position,expected",
        [(0, True), (1, True), (2, False)],
    )
    def test_correct_has_next(self, position, expected):
        history = _history("a", "b")

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
            history,
            position,
        )

        assert cursor.has_next is expected


class TestRejectNoneHistory:
    """A None history is rejected."""

    def test_reject_none_history(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
                None,
                0,
            )


class TestRejectNegativePosition:
    """A negative position is rejected."""

    def test_reject_negative_position(self):
        history = _history("first")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
                history,
                -1,
            )


class TestRejectOutOfRangePosition:
    """A position beyond session_count is rejected."""

    def test_reject_out_of_range_position(self):
        history = _history("first", "second")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
                history,
                3,
            )


class TestImmutableAndDeterministicOutput:
    """The cursor is a frozen dataclass and repeated builds agree."""

    def test_immutable_cursor(self):
        history = _history("first")

        cursor = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
            history,
            0,
        )

        assert dataclasses.is_dataclass(cursor)
        assert isinstance(
            cursor,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursor,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            cursor.position = 1

    def test_repeated_build_is_deterministic(self):
        history = _history("first", "second")

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder()

        first = builder.build(history, 1)
        second = builder.build(history, 1)

        assert first == second
        assert first is not second
