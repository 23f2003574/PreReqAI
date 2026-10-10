import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriber,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmark,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkFactory,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder,
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


def _execution_result(subscription):
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


def _entry(sequence_number):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryEntryBuilder().build(
        sequence_number,
        _execution_result(_subscription()),
    )


def _history(*sequence_numbers):
    entries = tuple(_entry(number) for number in sequence_numbers)

    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBuilder().build(
        entries
    )


def _cursor(history, position):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
        history,
        position,
    )


def _factory():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkFactory(
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder()
    )


class TestCreateBookmarkFromCursor:
    """create() captures the cursor's position in a bookmark."""

    def test_create_bookmark_from_cursor(self):
        history = _history(0, 1, 2)
        cursor = _cursor(history, 1)

        bookmark = _factory().create(cursor)

        assert bookmark.position == 1


class TestRestoreCursorFromBookmark:
    """restore() rebuilds a cursor at the bookmarked position."""

    def test_restore_cursor_from_bookmark(self):
        history = _history(0, 1, 2)
        cursor = _cursor(history, 1)

        factory = _factory()
        bookmark = factory.create(cursor)

        restored = factory.restore(history, bookmark)

        assert restored.position == 1
        assert restored == cursor


class TestRestoreBeginningPosition:
    """restore() correctly rebuilds a cursor at position 0."""

    def test_restore_beginning_position(self):
        history = _history(0, 1, 2)

        factory = _factory()
        bookmark = factory.create(_cursor(history, 0))

        restored = factory.restore(history, bookmark)

        assert restored.position == 0


class TestRestoreEndPosition:
    """restore() correctly rebuilds a cursor at the end position."""

    def test_restore_end_position(self):
        history = _history(0, 1, 2)

        factory = _factory()
        bookmark = factory.create(_cursor(history, 3))

        restored = factory.restore(history, bookmark)

        assert restored.position == 3
        assert restored.has_next is False


class TestRejectNoneCursor:
    """create() rejects a None cursor."""

    def test_reject_none_cursor(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError
        ):
            _factory().create(None)


class TestRejectNoneHistory:
    """restore() rejects a None history."""

    def test_reject_none_history(self):
        history = _history(0)
        bookmark = _factory().create(_cursor(history, 0))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError
        ):
            _factory().restore(None, bookmark)


class TestRejectNoneBookmark:
    """restore() rejects a None bookmark."""

    def test_reject_none_bookmark(self):
        history = _history(0)

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError
        ):
            _factory().restore(history, None)


class TestRejectBookmarkBeyondHistory:
    """restore() rejects a bookmark whose position exceeds the history."""

    def test_reject_bookmark_beyond_history(self):
        large_history = _history(0, 1, 2)
        small_history = _history(0)

        bookmark = _factory().create(_cursor(large_history, 3))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkError
        ):
            _factory().restore(small_history, bookmark)


class _CountingCursorBuilder:
    def __init__(self):
        self.calls = 0

    def build(self, history, position):
        self.calls += 1

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryCursorBuilder().build(
            history,
            position,
        )


class TestCursorBuilderInvokedDuringRestore:
    """The injected cursor builder is invoked exactly once per restore()."""

    def test_cursor_builder_invoked_during_restore(self):
        history = _history(0, 1)
        cursor_builder = _CountingCursorBuilder()

        factory = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmarkFactory(
            cursor_builder
        )

        bookmark = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleTransitionExecutionHistoryBookmark(
            position=1,
        )

        factory.restore(history, bookmark)

        assert cursor_builder.calls == 1


class TestDeterministicCreateRestoreBehavior:
    """Repeated create/restore cycles for the same cursor agree."""

    def test_deterministic_create_restore_behavior(self):
        history = _history(0, 1, 2)
        cursor = _cursor(history, 2)

        factory = _factory()

        first_bookmark = factory.create(cursor)
        second_bookmark = factory.create(cursor)

        assert first_bookmark == second_bookmark

        first_restored = factory.restore(history, first_bookmark)
        second_restored = factory.restore(history, second_bookmark)

        assert first_restored == second_restored
