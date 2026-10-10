import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkFactory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder,
)


class _Event:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"_Event({self.name!r})"


def _session(name):
    event = _Event(name)

    dispatch_result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResultBuilder().build(
        event,
        subscriber_count=1,
        successful_dispatch_count=1,
    )

    publication_result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationResultBuilder().build(
        event,
        resolved_subscriber_count=1,
        dispatch_result=dispatch_result,
    )

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationSessionBuilder().build(
        event,
        publication_result,
    )


def _history(*names):
    sessions = tuple(_session(name) for name in names)

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBuilder().build(
        sessions
    )


def _cursor(history, position):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder().build(
        history,
        position,
    )


def _factory():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkFactory(
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryCursorBuilder()
    )


class TestCreateBookmark:
    """create() captures the cursor position and history session count."""

    def test_create_bookmark(self):
        history = _history("first", "second", "third")
        cursor = _cursor(history, 1)

        bookmark = _factory().create(history, cursor)

        assert bookmark.position == 1
        assert bookmark.session_count == 3


class TestRestoreCursor:
    """restore() rebuilds a cursor equal to the original at that position."""

    def test_restore_cursor(self):
        history = _history("first", "second", "third")
        cursor = _cursor(history, 1)

        factory = _factory()
        bookmark = factory.create(history, cursor)
        restored = factory.restore(bookmark, history)

        assert restored == cursor


class TestBeginningPosition:
    """A bookmark at position 0 restores to position 0."""

    def test_beginning_position(self):
        history = _history("first", "second")
        cursor = _cursor(history, 0)

        factory = _factory()
        bookmark = factory.create(history, cursor)
        restored = factory.restore(bookmark, history)

        assert restored.position == 0


class TestMiddlePosition:
    """A bookmark mid-history restores to the same middle position."""

    def test_middle_position(self):
        history = _history("first", "second", "third")
        cursor = _cursor(history, 1)

        factory = _factory()
        bookmark = factory.create(history, cursor)
        restored = factory.restore(bookmark, history)

        assert restored.position == 1


class TestEndPosition:
    """A bookmark at the end restores to the end position."""

    def test_end_position(self):
        history = _history("first", "second")
        cursor = _cursor(history, 2)

        factory = _factory()
        bookmark = factory.create(history, cursor)
        restored = factory.restore(bookmark, history)

        assert restored.position == 2
        assert restored.has_next is False


class TestEmptyHistory:
    """A bookmark over an empty history round-trips correctly."""

    def test_empty_history(self):
        history = _history()
        cursor = _cursor(history, 0)

        factory = _factory()
        bookmark = factory.create(history, cursor)
        restored = factory.restore(bookmark, history)

        assert bookmark.position == 0
        assert bookmark.session_count == 0
        assert restored.position == 0


class TestRejectNoneHistory:
    """A None history is rejected by both create() and restore()."""

    def test_reject_none_history_create(self):
        history = _history("first")
        cursor = _cursor(history, 0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError
        ):
            _factory().create(None, cursor)

    def test_reject_none_history_restore(self):
        history = _history("first")
        cursor = _cursor(history, 0)

        factory = _factory()
        bookmark = factory.create(history, cursor)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError
        ):
            factory.restore(bookmark, None)


class TestRejectNoneCursor:
    """A None cursor is rejected by create()."""

    def test_reject_none_cursor(self):
        history = _history("first")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError
        ):
            _factory().create(history, None)


class TestRejectSessionCountMismatch:
    """restore() rejects a bookmark whose session_count no longer matches."""

    def test_reject_session_count_mismatch(self):
        original_history = _history("first", "second")
        cursor = _cursor(original_history, 1)

        factory = _factory()
        bookmark = factory.create(original_history, cursor)

        grown_history = _history("first", "second", "third")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventPublicationHistoryBookmarkError
        ):
            factory.restore(bookmark, grown_history)


class TestDeterministicSaveRestore:
    """Repeated create()/restore() round-trips agree."""

    def test_deterministic_save_restore(self):
        history = _history("first", "second", "third")
        cursor = _cursor(history, 2)

        factory = _factory()

        first_bookmark = factory.create(history, cursor)
        second_bookmark = factory.create(history, cursor)

        assert first_bookmark == second_bookmark
        assert first_bookmark is not second_bookmark

        first_restore = factory.restore(first_bookmark, history)
        second_restore = factory.restore(second_bookmark, history)

        assert first_restore == second_restore
        assert first_restore is not second_restore
