import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryError,
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


def _execution_result():
    subscription = _subscription()

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


class TestBuildValidHistoryEntry:
    """A history entry can be built for a valid sequence number and result."""

    def test_build_valid_history_entry(self):
        execution_result = _execution_result()

        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder().build(
            0,
            execution_result,
        )

        assert entry.sequence_number == 0
        assert entry.execution_result is execution_result


class TestSequenceNumberZero:
    """A sequence number of exactly 0 is accepted."""

    def test_sequence_number_zero(self):
        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder().build(
            0,
            _execution_result(),
        )

        assert entry.sequence_number == 0


class TestLargeSequenceNumber:
    """A large sequence number is accepted."""

    def test_large_sequence_number(self):
        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder().build(
            1_000_000,
            _execution_result(),
        )

        assert entry.sequence_number == 1_000_000


class TestPreserveExecutionResultReference:
    """The entry preserves the exact execution result reference passed in."""

    def test_preserve_execution_result_reference(self):
        execution_result = _execution_result()

        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder().build(
            5,
            execution_result,
        )

        assert entry.execution_result is execution_result


class TestRejectNegativeSequenceNumber:
    """A negative sequence number is rejected."""

    def test_reject_negative_sequence_number(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder().build(
                -1,
                _execution_result(),
            )


class TestRejectNoneExecutionResult:
    """A None execution result is rejected."""

    def test_reject_none_execution_result(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder().build(
                0,
                None,
            )


class TestImmutableEntry:
    """A built history entry cannot have its fields reassigned."""

    def test_immutable_entry(self):
        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder().build(
            0,
            _execution_result(),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.sequence_number = 1


class TestDeterministicConstruction:
    """Building the same inputs twice produces equal, distinct entries."""

    def test_deterministic_construction(self):
        execution_result = _execution_result()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder()

        first = builder.build(3, execution_result)
        second = builder.build(3, execution_result)

        assert first == second
        assert first is not second
        assert dataclasses.is_dataclass(first)
        assert isinstance(
            first,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntry,
        )


class TestCorrectSequenceAssignment:
    """The entry's sequence_number always mirrors the value passed to the builder."""

    @pytest.mark.parametrize("sequence_number", [0, 1, 42])
    def test_correct_sequence_assignment(self, sequence_number):
        entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder().build(
            sequence_number,
            _execution_result(),
        )

        assert entry.sequence_number == sequence_number


class TestEqualityForIdenticalEntries:
    """Two entries built from equal inputs compare equal."""

    def test_equality_for_identical_entries(self):
        execution_result = _execution_result()

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder()

        first = builder.build(2, execution_result)
        second = builder.build(2, execution_result)

        assert first == second
