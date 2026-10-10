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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError,
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


def _cursor(history, position):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
        history,
        position,
    )


class TestReadFirstEntry:
    """Reading at position 0 returns the first entry."""

    def test_read_first_entry(self):
        history = _history(0, 1, 2)
        cursor = _cursor(history, 0)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.entry is history.entries[0]
        assert result.entry_found is True


class TestReadMiddleEntry:
    """Reading at a middle position returns that entry."""

    def test_read_middle_entry(self):
        history = _history(0, 1, 2)
        cursor = _cursor(history, 1)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.entry is history.entries[1]
        assert result.entry_found is True


class TestReadLastEntry:
    """Reading at the final valid position returns the last entry."""

    def test_read_last_entry(self):
        history = _history(0, 1, 2)
        cursor = _cursor(history, 2)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.entry is history.entries[2]
        assert result.entry_found is True


class TestReadFromEmptyHistory:
    """Reading from an empty history at position 0 finds no entry."""

    def test_read_from_empty_history(self):
        history = _history()
        cursor = _cursor(history, 0)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.entry is None
        assert result.entry_found is False


class TestReadAtEndCursorReturnsNoEntry:
    """Reading at the end-of-history cursor position finds no entry."""

    def test_read_at_end_cursor_returns_no_entry(self):
        history = _history(0, 1)
        cursor = _cursor(history, 2)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.entry is None
        assert result.entry_found is False


class TestRejectNoneHistory:
    """A None history is rejected."""

    def test_reject_none_history(self):
        history = _history(0)
        cursor = _cursor(history, 0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader().read(
                None,
                cursor,
            )


class TestRejectNoneCursor:
    """A None cursor is rejected."""

    def test_reject_none_cursor(self):
        history = _history(0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader().read(
                history,
                None,
            )


class TestRejectCursorBeyondHistory:
    """A cursor built against a different, smaller history is rejected."""

    def test_reject_cursor_beyond_history(self):
        small_history = _history(0)
        cursor = _cursor(small_history, 1)

        larger_history = _history(0, 1, 2)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReaderError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader().read(
                small_history,
                _cursor(larger_history, 3),
            )


class TestCursorRemainsUnchanged:
    """The reader returns the exact cursor it was given, unmodified."""

    def test_cursor_remains_unchanged(self):
        history = _history(0, 1)
        cursor = _cursor(history, 0)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader().read(
            history,
            cursor,
        )

        assert result.cursor is cursor


class TestDeterministicReads:
    """Reading the same history and cursor twice produces equal results."""

    def test_deterministic_reads(self):
        history = _history(0, 1)
        cursor = _cursor(history, 0)

        reader = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryReader()

        first = reader.read(history, cursor)
        second = reader.read(history, cursor)

        assert first == second
