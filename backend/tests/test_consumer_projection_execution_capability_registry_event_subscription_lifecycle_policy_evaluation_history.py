import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryError,
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


class TestBuildEmptyHistory:
    """An empty entry collection builds an empty history."""

    def test_build_empty_history(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder().build(
            ()
        )

        assert history.entries == ()
        assert history.entry_count == 0


class TestBuildSingleEntryHistory:
    """A single entry builds a history of length one."""

    def test_build_single_entry_history(self):
        entry = _entry(0)

        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder().build(
            (entry,)
        )

        assert history.entries == (entry,)
        assert history.entry_count == 1


class TestBuildMultiEntryHistory:
    """Multiple entries with increasing sequence numbers build a valid history."""

    def test_build_multi_entry_history(self):
        entries = (_entry(0), _entry(1), _entry(2))

        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder().build(
            entries
        )

        assert history.entries == entries
        assert history.entry_count == 3


class TestCorrectEntryCount:
    """entry_count always mirrors the number of entries supplied."""

    @pytest.mark.parametrize("count", [0, 1, 5])
    def test_correct_entry_count(self, count):
        entries = tuple(_entry(index) for index in range(count))

        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder().build(
            entries
        )

        assert history.entry_count == count


class TestRejectNoneEntries:
    """A None entry collection is rejected."""

    def test_reject_none_entries(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder().build(
                None
            )


class TestRejectNoneHistoryEntry:
    """A None entry within the collection is rejected."""

    def test_reject_none_history_entry(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder().build(
                (_entry(0), None)
            )


class TestRejectDuplicateSequenceNumbers:
    """Duplicate sequence numbers are rejected."""

    def test_reject_duplicate_sequence_numbers(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder().build(
                (_entry(0), _entry(0))
            )


class TestRejectOutOfOrderSequenceNumbers:
    """Non-monotonic sequence numbers are rejected."""

    def test_reject_out_of_order_sequence_numbers(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder().build(
                (_entry(1), _entry(0))
            )


class TestPreserveChronologicalOrdering:
    """The history preserves the exact order of the entries supplied."""

    def test_preserve_chronological_ordering(self):
        entries = (_entry(0), _entry(1), _entry(2))

        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder().build(
            entries
        )

        assert tuple(
            entry.sequence_number for entry in history.entries
        ) == (0, 1, 2)


class TestDeterministicConstruction:
    """Building the same entries twice produces equal, distinct histories."""

    def test_deterministic_construction(self):
        entries = (_entry(0), _entry(1))

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryBuilder()

        first = builder.build(entries)
        second = builder.build(entries)

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistory,
        )
