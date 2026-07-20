import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder,
)


class _Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"_Event({self.name!r})"


def _session(name, subscriber_count=1, successful_dispatch_count=1):
    event = _Event(name)

    dispatch_result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
        event,
        subscriber_count=subscriber_count,
        successful_dispatch_count=successful_dispatch_count,
    )

    publication_result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
        event,
        resolved_subscriber_count=subscriber_count,
        dispatch_result=dispatch_result,
    )

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
        event,
        publication_result,
    )


class TestEmptyHistory:
    """An empty session collection produces an empty history."""

    def test_empty_history(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
            ()
        )

        assert history.sessions == ()
        assert history.session_count == 0


class TestSingleSessionHistory:
    """A single session produces a history of length one."""

    def test_single_session_history(self):
        session = _session("registered")

        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
            (session,)
        )

        assert history.sessions == (session,)
        assert history.session_count == 1


class TestMultipleSessionHistory:
    """Every supplied session is included in the history."""

    def test_multiple_session_history(self):
        first = _session("first")
        second = _session("second")
        third = _session("third")

        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
            (first, second, third)
        )

        assert history.sessions == (first, second, third)
        assert history.session_count == 3


class TestSessionOrderingPreserved:
    """Sessions retain the exact order they were supplied in."""

    def test_session_ordering_preserved(self):
        sessions = tuple(
            _session(str(index)) for index in range(5)
        )

        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
            sessions
        )

        assert history.sessions == sessions


class TestCorrectSessionCount:
    """session_count always equals len(sessions)."""

    @pytest.mark.parametrize("count", [0, 1, 4])
    def test_correct_session_count(self, count):
        sessions = tuple(
            _session(str(index)) for index in range(count)
        )

        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
            sessions
        )

        assert history.session_count == count


class TestRejectNoneCollection:
    """A None session collection is rejected."""

    def test_reject_none_collection(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
                None
            )


class TestRejectNoneSession:
    """A None entry within the session collection is rejected."""

    def test_reject_none_session(self):
        session = _session("registered")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
                (session, None)
            )


class TestImmutableHistory:
    """The history is a frozen dataclass."""

    def test_immutable_history(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
            ()
        )

        assert dataclasses.is_dataclass(history)
        assert isinstance(
            history,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistory,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            history.session_count = 1


class TestSessionsPreservedByReference:
    """Sessions are stored as-is, not copied or rebuilt."""

    def test_sessions_preserved_by_reference(self):
        session = _session("registered")

        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
            (session,)
        )

        assert history.sessions[0] is session


class TestDeterminism:
    """Building the same sessions twice produces equal histories."""

    def test_repeated_build_is_deterministic(self):
        sessions = (_session("first"), _session("second"))

        builder = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder()

        first = builder.build(sessions)
        second = builder.build(sessions)

        assert first == second
        assert first is not second
