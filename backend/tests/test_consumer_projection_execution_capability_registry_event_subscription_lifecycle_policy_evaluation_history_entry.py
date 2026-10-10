import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryError,
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


class TestBuildValidHistoryEntry:
    """A history entry can be built for a valid sequence number and result."""

    def test_build_valid_history_entry(self):
        evaluation_result = _evaluation_result()

        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder().build(
            0,
            evaluation_result,
        )

        assert entry.sequence_number == 0
        assert entry.evaluation_result is evaluation_result


class TestSequenceNumberZero:
    """A sequence number of exactly 0 is accepted."""

    def test_sequence_number_zero(self):
        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder().build(
            0,
            _evaluation_result(),
        )

        assert entry.sequence_number == 0


class TestLargeSequenceNumber:
    """A large sequence number is accepted."""

    def test_large_sequence_number(self):
        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder().build(
            1_000_000,
            _evaluation_result(),
        )

        assert entry.sequence_number == 1_000_000


class TestPreserveEvaluationResultReference:
    """The entry preserves the exact evaluation result reference passed in."""

    def test_preserve_evaluation_result_reference(self):
        evaluation_result = _evaluation_result()

        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder().build(
            5,
            evaluation_result,
        )

        assert entry.evaluation_result is evaluation_result


class TestRejectNegativeSequenceNumber:
    """A negative sequence number is rejected."""

    def test_reject_negative_sequence_number(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder().build(
                -1,
                _evaluation_result(),
            )


class TestRejectNoneEvaluationResult:
    """A None evaluation result is rejected."""

    def test_reject_none_evaluation_result(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder().build(
                0,
                None,
            )


class TestImmutableEntry:
    """A built history entry cannot have its fields reassigned."""

    def test_immutable_entry(self):
        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder().build(
            0,
            _evaluation_result(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.sequence_number = 1


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct entries."""

    def test_deterministic_construction(self):
        evaluation_result = _evaluation_result()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder()

        first = builder.build(3, evaluation_result)
        second = builder.build(3, evaluation_result)

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntry,
        )


class TestCorrectSequenceAssignment:
    """The entry's sequence_number always mirrors the value passed to the builder."""

    @pytest.mark.parametrize("sequence_number", [0, 1, 42])
    def test_correct_sequence_assignment(self, sequence_number):
        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder().build(
            sequence_number,
            _evaluation_result(),
        )

        assert entry.sequence_number == sequence_number


class TestEqualityForIdenticalEntries:
    """Two entries built from equal inputs compare equal."""

    def test_equality_for_identical_entries(self):
        evaluation_result = _evaluation_result()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyEvaluationHistoryEntryBuilder()

        first = builder.build(2, evaluation_result)
        second = builder.build(2, evaluation_result)

        assert first == second
