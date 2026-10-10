import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpoint,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder,
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


def _cursor(history, position):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
        history,
        position,
    )


class TestBuildCheckpointForEmptyHistory:
    """A checkpoint over an empty history reports is_empty True."""

    def test_build_checkpoint_for_empty_history(self):
        history = _history()
        cursor = _cursor(history, 0)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.session_count == 0
        assert checkpoint.last_position == 0
        assert checkpoint.is_empty is True


class TestBuildCheckpointAtBeginning:
    """A checkpoint at position 0 reports the beginning of a non-empty history."""

    def test_build_checkpoint_at_beginning(self):
        history = _history("first", "second", "third")
        cursor = _cursor(history, 0)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.last_position == 0
        assert checkpoint.is_empty is False


class TestBuildCheckpointInMiddle:
    """A checkpoint mid-history reports that exact position."""

    def test_build_checkpoint_in_middle(self):
        history = _history("first", "second", "third")
        cursor = _cursor(history, 1)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.last_position == 1
        assert checkpoint.is_empty is False


class TestBuildCheckpointAtEnd:
    """A checkpoint at the final position reports session_count as last_position."""

    def test_build_checkpoint_at_end(self):
        history = _history("first", "second", "third")
        cursor = _cursor(history, 3)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.last_position == 3
        assert checkpoint.session_count == 3


class TestCorrectSessionCount:
    """session_count always mirrors history.session_count."""

    @pytest.mark.parametrize("count", [0, 1, 4])
    def test_correct_session_count(self, count):
        history = _history(*[str(index) for index in range(count)])
        cursor = _cursor(history, 0)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.session_count == count


class TestCorrectLastPosition:
    """last_position always mirrors cursor.position."""

    @pytest.mark.parametrize("position", [0, 1, 2])
    def test_correct_last_position(self, position):
        history = _history("first", "second")
        cursor = _cursor(history, position)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.last_position == position


class TestCorrectIsEmpty:
    """is_empty is true exactly when history.session_count is zero."""

    @pytest.mark.parametrize(
        "count,expected",
        [(0, True), (1, False), (3, False)],
    )
    def test_correct_is_empty(self, count, expected):
        history = _history(*[str(index) for index in range(count)])
        cursor = _cursor(history, 0)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.is_empty is expected


class TestRejectNoneHistory:
    """A None history is rejected."""

    def test_reject_none_history(self):
        history = _history("first")
        cursor = _cursor(history, 0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder().build(
                None,
                cursor,
            )


class TestRejectNoneCursor:
    """A None cursor is rejected."""

    def test_reject_none_cursor(self):
        history = _history("first")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder().build(
                history,
                None,
            )


class TestDeterministicOutput:
    """Building the same inputs twice produces equal, distinct checkpoints."""

    def test_deterministic_output(self):
        history = _history("first", "second")
        cursor = _cursor(history, 1)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpointBuilder()

        first = builder.build(history, cursor)
        second = builder.build(history, cursor)

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCheckpoint,
        )
