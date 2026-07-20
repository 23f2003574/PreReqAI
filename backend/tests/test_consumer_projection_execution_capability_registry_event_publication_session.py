import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionError,
)


class _Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"_Event({self.name!r})"


def _publication_result(event, subscriber_count, successful_dispatch_count):
    dispatch_result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
        event,
        subscriber_count=subscriber_count,
        successful_dispatch_count=successful_dispatch_count,
    )

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
        event,
        resolved_subscriber_count=subscriber_count,
        dispatch_result=dispatch_result,
    )


class TestBuildValidSession:
    """A well-formed input set builds a matching publication session."""

    def test_build_valid_session(self):
        event = _Event("registered")
        publication_result = _publication_result(event, 3, 3)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
            event,
            publication_result,
        )

        assert session.event is event
        assert session.publication_result is publication_result


class TestZeroSubscriberPublication:
    """A publication resolved to zero subscribers is completed."""

    def test_zero_subscriber_publication(self):
        event = _Event("registered")
        publication_result = _publication_result(event, 0, 0)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
            event,
            publication_result,
        )

        assert session.subscriber_count == 0
        assert session.publication_completed is True


class TestSuccessfulPublicationSession:
    """A fully completed publication produces a completed session."""

    def test_successful_publication_session(self):
        event = _Event("registered")
        publication_result = _publication_result(event, 2, 2)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
            event,
            publication_result,
        )

        assert session.publication_completed is True


class TestIncompletePublicationSession:
    """A partially completed publication produces an incomplete session."""

    def test_incomplete_publication_session(self):
        event = _Event("registered")
        publication_result = _publication_result(event, 3, 1)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
            event,
            publication_result,
        )

        assert session.publication_completed is False


class TestCorrectSubscriberCount:
    """subscriber_count mirrors publication_result.resolved_subscriber_count."""

    @pytest.mark.parametrize("subscriber_count", [0, 1, 4])
    def test_correct_subscriber_count(self, subscriber_count):
        event = _Event("registered")
        publication_result = _publication_result(
            event,
            subscriber_count,
            subscriber_count,
        )

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
            event,
            publication_result,
        )

        assert session.subscriber_count == subscriber_count
        assert (
            session.subscriber_count
            == publication_result.resolved_subscriber_count
        )


class TestCorrectPublicationStatus:
    """publication_completed mirrors publication_result.published exactly."""

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
    def test_correct_publication_status(
        self,
        subscriber_count,
        successful_dispatch_count,
        expected,
    ):
        event = _Event("registered")
        publication_result = _publication_result(
            event,
            subscriber_count,
            successful_dispatch_count,
        )

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
            event,
            publication_result,
        )

        assert session.publication_completed is expected
        assert session.publication_completed == publication_result.published


class TestRejectNoneEvent:
    """A None event is rejected."""

    def test_reject_none_event(self):
        publication_result = _publication_result(_Event("registered"), 1, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
                None,
                publication_result,
            )


class TestRejectNonePublicationResult:
    """A None publication result is rejected."""

    def test_reject_none_publication_result(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
                _Event("registered"),
                None,
            )


class TestRejectEventMismatch:
    """A publication result built for a different event is rejected."""

    def test_reject_event_mismatch(self):
        session_event = _Event("registered")
        publication_result = _publication_result(_Event("removed"), 1, 1)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
                session_event,
                publication_result,
            )


class TestImmutableAndDeterministicSession:
    """The session is a frozen dataclass and repeated builds agree."""

    def test_immutable_session(self):
        event = _Event("registered")
        publication_result = _publication_result(event, 1, 1)

        session = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
            event,
            publication_result,
        )

        assert dataclasses.is_dataclass(session)
        assert isinstance(
            session,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSession,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            session.publication_completed = False

    def test_repeated_build_is_deterministic(self):
        event = _Event("registered")
        publication_result = _publication_result(event, 2, 2)

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder()

        first = builder.build(event, publication_result)
        second = builder.build(event, publication_result)

        assert first == second
        assert first is not second
