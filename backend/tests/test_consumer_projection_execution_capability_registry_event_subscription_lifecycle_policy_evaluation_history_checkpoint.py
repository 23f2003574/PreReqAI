import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCursorBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder,
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


class TestBuildCheckpointForEmptyHistory:
    """A checkpoint over an empty history reports is_empty True."""

    def test_build_checkpoint_for_empty_history(self):
        history = _history()
        cursor = _cursor(history, 0)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.entry_count == 0
        assert checkpoint.last_position == 0
        assert checkpoint.is_empty is True


class TestBuildCheckpointAtBeginning:
    """A checkpoint at position 0 reports the beginning of a non-empty history."""

    def test_build_checkpoint_at_beginning(self):
        history = _history(0, 1, 2)
        cursor = _cursor(history, 0)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.last_position == 0
        assert checkpoint.is_empty is False


class TestBuildCheckpointInMiddle:
    """A checkpoint mid-history reports that exact position."""

    def test_build_checkpoint_in_middle(self):
        history = _history(0, 1, 2)
        cursor = _cursor(history, 1)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.last_position == 1
        assert checkpoint.is_empty is False


class TestBuildCheckpointAtEnd:
    """A checkpoint at the final position reports entry_count as last_position."""

    def test_build_checkpoint_at_end(self):
        history = _history(0, 1, 2)
        cursor = _cursor(history, 3)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.last_position == 3
        assert checkpoint.entry_count == 3


class TestCorrectEntryCount:
    """entry_count always mirrors history.entry_count."""

    @pytest.mark.parametrize("count", [0, 1, 4])
    def test_correct_entry_count(self, count):
        history = _history(*range(count))
        cursor = _cursor(history, 0)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.entry_count == count


class TestCorrectLastPosition:
    """last_position always mirrors cursor.position."""

    @pytest.mark.parametrize("position", [0, 1, 2])
    def test_correct_last_position(self, position):
        history = _history(0, 1)
        cursor = _cursor(history, position)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.last_position == position


class TestCorrectIsEmpty:
    """is_empty is true exactly when history.entry_count is zero."""

    @pytest.mark.parametrize(
        "count,expected",
        [(0, True), (1, False), (3, False)],
    )
    def test_correct_is_empty(self, count, expected):
        history = _history(*range(count))
        cursor = _cursor(history, 0)

        checkpoint = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder().build(
            history,
            cursor,
        )

        assert checkpoint.is_empty is expected


class TestRejectNoneHistory:
    """A None history is rejected."""

    def test_reject_none_history(self):
        history = _history(0)
        cursor = _cursor(history, 0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder().build(
                None,
                cursor,
            )


class TestRejectNoneCursor:
    """A None cursor is rejected."""

    def test_reject_none_cursor(self):
        history = _history(0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder().build(
                history,
                None,
            )


class TestRejectCursorBeyondHistory:
    """A cursor whose position exceeds the history is rejected."""

    def test_reject_cursor_beyond_history(self):
        small_history = _history(0)
        larger_history = _history(0, 1, 2)
        cursor = _cursor(larger_history, 3)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryCheckpointBuilder().build(
                small_history,
                cursor,
            )
