import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError,
)


class _Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"_Event({self.name!r})"


def _dispatch_result(event, subscriber_count, successful_dispatch_count):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
        event,
        subscriber_count=subscriber_count,
        successful_dispatch_count=successful_dispatch_count,
    )


class TestBuildValidPublicationResult:
    """A well-formed input set builds a matching publication result."""

    def test_build_valid_publication_result(self):
        event = _Event("registered")
        dispatch_result = _dispatch_result(event, 3, 3)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
            event,
            resolved_subscriber_count=3,
            dispatch_result=dispatch_result,
        )

        assert result.event is event
        assert result.resolved_subscriber_count == 3
        assert result.dispatch_result is dispatch_result


class TestZeroSubscribers:
    """A publication resolved to zero subscribers is published."""

    def test_zero_subscribers(self):
        event = _Event("registered")
        dispatch_result = _dispatch_result(event, 0, 0)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
            event,
            resolved_subscriber_count=0,
            dispatch_result=dispatch_result,
        )

        assert result.resolved_subscriber_count == 0
        assert result.published is True


class TestSuccessfulPublication:
    """A fully completed dispatch produces a published result."""

    def test_successful_publication(self):
        event = _Event("registered")
        dispatch_result = _dispatch_result(event, 2, 2)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
            event,
            resolved_subscriber_count=2,
            dispatch_result=dispatch_result,
        )

        assert result.published is True


class TestIncompletePublication:
    """A partially completed dispatch produces an unpublished result."""

    def test_incomplete_publication(self):
        event = _Event("registered")
        dispatch_result = _dispatch_result(event, 3, 1)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
            event,
            resolved_subscriber_count=3,
            dispatch_result=dispatch_result,
        )

        assert result.published is False


class TestCorrectPublishedComputation:
    """published mirrors dispatch_result.completed exactly."""

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
    def test_published_computation(
        self,
        subscriber_count,
        successful_dispatch_count,
        expected,
    ):
        event = _Event("registered")
        dispatch_result = _dispatch_result(
            event,
            subscriber_count,
            successful_dispatch_count,
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
            event,
            resolved_subscriber_count=subscriber_count,
            dispatch_result=dispatch_result,
        )

        assert result.published is expected
        assert result.published == dispatch_result.completed


class TestRejectNoneEvent:
    """A None event is rejected."""

    def test_reject_none_event(self):
        dispatch_result = _dispatch_result(_Event("registered"), 1, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
                None,
                resolved_subscriber_count=1,
                dispatch_result=dispatch_result,
            )


class TestRejectNoneDispatchResult:
    """A None dispatch result is rejected."""

    def test_reject_none_dispatch_result(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
                _Event("registered"),
                resolved_subscriber_count=1,
                dispatch_result=None,
            )


class TestRejectNegativeSubscriberCount:
    """A negative resolved_subscriber_count is rejected."""

    def test_reject_negative_subscriber_count(self):
        event = _Event("registered")
        dispatch_result = _dispatch_result(event, 1, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
                event,
                resolved_subscriber_count=-1,
                dispatch_result=dispatch_result,
            )


class TestRejectEventMismatch:
    """A dispatch result built for a different event is rejected."""

    def test_reject_event_mismatch(self):
        published_event = _Event("registered")
        dispatch_result = _dispatch_result(_Event("removed"), 1, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
                published_event,
                resolved_subscriber_count=1,
                dispatch_result=dispatch_result,
            )


class TestRejectSubscriberCountMismatch:
    """A resolved_subscriber_count disagreeing with the dispatch result is rejected."""

    def test_reject_subscriber_count_mismatch(self):
        event = _Event("registered")
        dispatch_result = _dispatch_result(event, 3, 3)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
                event,
                resolved_subscriber_count=2,
                dispatch_result=dispatch_result,
            )


class TestImmutableAndDeterministicResult:
    """The result is a frozen dataclass and repeated builds agree."""

    def test_immutable_result(self):
        event = _Event("registered")
        dispatch_result = _dispatch_result(event, 1, 1)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
            event,
            resolved_subscriber_count=1,
            dispatch_result=dispatch_result,
        )

        assert dataclasses.is_dataclass(result)
        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResult,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.published = False

    def test_repeated_build_is_deterministic(self):
        event = _Event("registered")
        dispatch_result = _dispatch_result(event, 2, 2)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder()

        first = builder.build(
            event,
            resolved_subscriber_count=2,
            dispatch_result=dispatch_result,
        )
        second = builder.build(
            event,
            resolved_subscriber_count=2,
            dispatch_result=dispatch_result,
        )

        assert first == second
        assert first is not second
