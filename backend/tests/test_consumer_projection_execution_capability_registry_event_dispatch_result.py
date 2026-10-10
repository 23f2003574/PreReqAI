import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError,
)


class _Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"_Event({self.name!r})"


class TestBuildValidResult:
    """A well-formed input set builds a matching result."""

    def test_build_valid_result(self):
        event = _Event("registered")

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
            event,
            subscriber_count=3,
            successful_dispatch_count=3,
        )

        assert result.event is event
        assert result.subscriber_count == 3
        assert result.successful_dispatch_count == 3


class TestZeroSubscribers:
    """A dispatch to zero subscribers is treated as completed."""

    def test_zero_subscribers(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
            _Event("registered"),
            subscriber_count=0,
            successful_dispatch_count=0,
        )

        assert result.subscriber_count == 0
        assert result.successful_dispatch_count == 0
        assert result.completed is True


class TestPartialCompletion:
    """Fewer successes than subscribers means completed is False."""

    def test_partial_completion(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
            _Event("registered"),
            subscriber_count=3,
            successful_dispatch_count=1,
        )

        assert result.completed is False


class TestFullCompletion:
    """Successes equal to subscribers means completed is True."""

    def test_full_completion(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
            _Event("registered"),
            subscriber_count=4,
            successful_dispatch_count=4,
        )

        assert result.completed is True


class TestCorrectCompletedComputation:
    """completed is derived exactly from the two counts, in both directions."""

    @pytest.mark.parametrize(
        "subscriber_count,successful_dispatch_count,expected",
        [
            (0, 0, True),
            (1, 0, False),
            (1, 1, True),
            (5, 4, False),
            (5, 5, True),
        ],
    )
    def test_completed_computation(
        self,
        subscriber_count,
        successful_dispatch_count,
        expected,
    ):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
            _Event("registered"),
            subscriber_count=subscriber_count,
            successful_dispatch_count=successful_dispatch_count,
        )

        assert result.completed is expected


class TestRejectNoneEvent:
    """A None event is rejected."""

    def test_reject_none_event(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
                None,
                subscriber_count=1,
                successful_dispatch_count=1,
            )


class TestRejectNegativeSubscriberCount:
    """A negative subscriber_count is rejected."""

    def test_reject_negative_subscriber_count(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
                _Event("registered"),
                subscriber_count=-1,
                successful_dispatch_count=0,
            )


class TestRejectInvalidSuccessfulDispatchCount:
    """A negative or over-large successful_dispatch_count is rejected."""

    def test_reject_negative_successful_dispatch_count(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
                _Event("registered"),
                subscriber_count=1,
                successful_dispatch_count=-1,
            )

    def test_reject_successful_dispatch_count_greater_than_subscriber_count(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
                _Event("registered"),
                subscriber_count=1,
                successful_dispatch_count=2,
            )


class TestImmutableResult:
    """The result is a frozen dataclass; fields cannot be reassigned."""

    def test_immutable_result(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
            _Event("registered"),
            subscriber_count=1,
            successful_dispatch_count=1,
        )

        assert dataclasses.is_dataclass(result)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.completed = False


class TestDeterminism:
    """Building the same inputs twice produces equal results."""

    def test_repeated_build_is_deterministic(self):
        event = _Event("registered")

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder()

        first = builder.build(
            event,
            subscriber_count=2,
            successful_dispatch_count=2,
        )
        second = builder.build(
            event,
            subscriber_count=2,
            successful_dispatch_count=2,
        )

        assert first == second
        assert first is not second


class TestResultIsDataclassType:
    """The result is an instance of the canonical dispatch result type."""

    def test_result_is_dataclass_type(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
            _Event("registered"),
            subscriber_count=1,
            successful_dispatch_count=1,
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult,
        )
