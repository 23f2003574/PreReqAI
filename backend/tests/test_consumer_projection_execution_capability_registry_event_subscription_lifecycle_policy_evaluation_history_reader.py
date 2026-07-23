import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursorBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReaderError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
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


def _evaluation_result():
    policy = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            _STATE.REGISTERED,
            _STATE.ACTIVE,
        ),
        _STATE.REGISTERED,
    )

    transition = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder().build(
        _subscription(),
        _STATE.REGISTERED,
        _STATE.ACTIVE,
    )

    request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationRequestBuilder().build(
        policy,
        transition,
    )

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationResultBuilder().build(
        request,
        True,
    )


def _entry(sequence_number):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder().build(
        sequence_number,
        _evaluation_result(),
    )


def _history(*sequence_numbers):
    entries = tuple(_entry(number) for number in sequence_numbers)

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder().build(
        entries
    )


def _cursor(history, position):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursorBuilder().build(
        history,
        position,
    )


class TestReadFirstEntry:
    """Reading at position 0 returns the first entry."""

    def test_read_first_entry(self):
        history = _history(0, 1, 2)
        cursor = _cursor(history, 0)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader().read(
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

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader().read(
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

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader().read(
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

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader().read(
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

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader().read(
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
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReaderError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader().read(
                None,
                cursor,
            )


class TestRejectNoneCursor:
    """A None cursor is rejected."""

    def test_reject_none_cursor(self):
        history = _history(0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReaderError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader().read(
                history,
                None,
            )


class TestRejectCursorBeyondHistory:
    """A cursor built against a different, larger history is rejected."""

    def test_reject_cursor_beyond_history(self):
        small_history = _history(0)

        larger_history = _history(0, 1, 2)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReaderError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader().read(
                small_history,
                _cursor(larger_history, 3),
            )


class TestCursorRemainsUnchanged:
    """The reader returns the exact cursor it was given, unmodified."""

    def test_cursor_remains_unchanged(self):
        history = _history(0, 1)
        cursor = _cursor(history, 0)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader().read(
            history,
            cursor,
        )

        assert result.cursor is cursor


class TestDeterministicReads:
    """Reading the same history and cursor twice produces equal results."""

    def test_deterministic_reads(self):
        history = _history(0, 1)
        cursor = _cursor(history, 0)

        reader = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryReader()

        first = reader.read(history, cursor)
        second = reader.read(history, cursor)

        assert first == second
