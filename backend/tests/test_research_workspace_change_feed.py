from concurrent.futures import (
    ThreadPoolExecutor,
)

import pytest

from backend.session import (
    ResearchWorkspaceChangeFeed,
    ResearchWorkspaceChangeOperation,
    ResearchWorkspaceEventBus,
)


def create_change_feed(

    event_bus=None,

):

    return (

        ResearchWorkspaceChangeFeed(

            event_bus=event_bus
        )
    )


def append_session_created(

    feed,

    entity_id="session-a",

):

    return feed.append(

        operation=(

            ResearchWorkspaceChangeOperation
            .CREATED
        ),

        entity_type="session",

        entity_id=entity_id,
    )


def create_change_feed_with_events(

    count,

):

    feed = create_change_feed()

    for index in range(count):

        append_session_created(

            feed,

            entity_id=f"session-{index}",
        )

    return feed


def test_workspace_change_events_receive_monotonic_sequences():

    feed = create_change_feed()

    first = append_session_created(
        feed
    )

    second = feed.append(

        operation=(

            ResearchWorkspaceChangeOperation
            .UPDATED
        ),

        entity_type="session",

        entity_id="session-a",
    )

    assert (

        second.sequence

        == first.sequence + 1
    )


def test_change_feed_sequence_survives_restart(

    tmp_path,

):

    storage_path = (

        tmp_path

        / "changes.json"
    )

    feed = (

        ResearchWorkspaceChangeFeed(

            storage_path=storage_path
        )
    )

    first = append_session_created(
        feed
    )

    restarted = (

        ResearchWorkspaceChangeFeed(

            storage_path=storage_path
        )
    )

    second = append_session_created(

        restarted,

        entity_id="session-b",
    )

    assert (

        second.sequence

        == first.sequence + 1
    )


def test_change_feed_supports_cursor_pagination():

    feed = (

        create_change_feed_with_events(
            5
        )
    )

    first_page = (

        feed.get_changes(

            after_sequence=0,

            limit=2,
        )
    )

    assert (

        len(
            first_page.events
        )

        == 2
    )

    assert first_page.has_more is True

    second_page = (

        feed.get_changes(

            after_sequence=(

                first_page
                .next_cursor
            ),

            limit=2,
        )
    )

    assert (

        second_page.events[0]
        .sequence

        > first_page.events[-1]
        .sequence
    )


def test_cursor_query_does_not_repeat_consumed_events():

    feed = (

        create_change_feed_with_events(
            4
        )
    )

    page = feed.get_changes(

        after_sequence=0,

        limit=4,
    )

    next_page = (

        feed.get_changes(

            after_sequence=(
                page.next_cursor
            )
        )
    )

    assert next_page.events == []


def test_filtered_cursor_skips_unrelated_events():

    feed = create_change_feed()

    append_session_created(
        feed
    )

    feed.append(

        operation=(

            ResearchWorkspaceChangeOperation
            .CREATED
        ),

        entity_type="checkpoint",

        entity_id="checkpoint-a",
    )

    append_session_created(

        feed,

        entity_id="session-b",
    )

    page = feed.get_changes(

        after_sequence=0,

        entity_types={
            "session"
        },
    )

    assert (

        [
            event.entity_id

            for event

            in page.events
        ]

        == [

            "session-a",

            "session-b",
        ]
    )

    assert page.next_cursor == 3


def test_change_feed_limit_must_be_positive():

    feed = create_change_feed()

    with pytest.raises(
        ValueError
    ):

        feed.get_changes(

            after_sequence=0,

            limit=0,
        )


def test_subscriber_receives_matching_change_events():

    bus = (
        ResearchWorkspaceEventBus()
    )

    feed = create_change_feed(
        bus
    )

    received = []

    bus.subscribe(
        received.append
    )

    event = append_session_created(
        feed
    )

    assert received == [
        event
    ]


def test_subscription_filters_by_entity_type():

    bus = (
        ResearchWorkspaceEventBus()
    )

    feed = create_change_feed(
        bus
    )

    received = []

    bus.subscribe(

        callback=(
            received.append
        ),

        entity_types={
            "session"
        },
    )

    feed.append(

        operation=(

            ResearchWorkspaceChangeOperation
            .CREATED
        ),

        entity_type="checkpoint",

        entity_id="checkpoint-a",
    )

    append_session_created(
        feed
    )

    assert len(received) == 1

    assert (

        received[0].entity_type

        == "session"
    )


def test_subscription_filters_by_operation():

    bus = (
        ResearchWorkspaceEventBus()
    )

    feed = create_change_feed(
        bus
    )

    received = []

    bus.subscribe(

        callback=(
            received.append
        ),

        operations={
            "deleted"
        },
    )

    append_session_created(
        feed
    )

    feed.append(

        operation=(

            ResearchWorkspaceChangeOperation
            .DELETED
        ),

        entity_type="session",

        entity_id="session-a",
    )

    assert len(received) == 1

    assert (

        received[0].operation

        == ResearchWorkspaceChangeOperation
        .DELETED
    )


def test_unsubscribed_callback_receives_no_future_events():

    bus = (
        ResearchWorkspaceEventBus()
    )

    feed = create_change_feed(
        bus
    )

    received = []

    subscription = (

        bus.subscribe(
            received.append
        )
    )

    bus.unsubscribe(

        subscription
        .subscription_id
    )

    append_session_created(
        feed
    )

    assert received == []


def test_broken_subscriber_does_not_block_other_subscribers():

    bus = (
        ResearchWorkspaceEventBus()
    )

    feed = create_change_feed(
        bus
    )

    received = []

    def broken_callback(
        event,
    ):

        raise RuntimeError(
            "subscriber failed"
        )

    bus.subscribe(
        broken_callback
    )

    bus.subscribe(
        received.append
    )

    event = append_session_created(
        feed
    )

    assert received == [
        event
    ]

    page = feed.get_changes(
        after_sequence=0
    )

    assert page.events == [
        event
    ]


def test_concurrent_change_appends_receive_unique_sequences():

    feed = create_change_feed()

    def append_event(index):

        return append_session_created(

            feed,

            entity_id=f"session-{index}",
        )

    with ThreadPoolExecutor(

        max_workers=8

    ) as executor:

        events = list(

            executor.map(

                append_event,

                range(100),
            )
        )

    sequences = [

        event.sequence

        for event

        in events
    ]

    assert (

        len(sequences)

        == len(
            set(sequences)
        )
    )

    assert (

        sorted(sequences)

        == list(
            range(1, 101)
        )
    )


def test_mutating_returned_change_event_does_not_mutate_feed():

    feed = create_change_feed()

    append_session_created(
        feed
    )

    page = feed.get_changes()

    page.events[0].metadata[
        "corrupted"
    ] = True

    fresh_page = feed.get_changes()

    assert (

        "corrupted"

        not in fresh_page.events[0]
        .metadata
    )


def test_export_and_restore_state_round_trips():

    feed = create_change_feed()

    append_session_created(
        feed
    )

    state = feed.export_state()

    restored = create_change_feed()

    restored.restore_state(
        state
    )

    assert (

        restored.latest_sequence

        == feed.latest_sequence
    )

    assert (

        len(
            restored
            .get_changes()
            .events
        )

        == 1
    )
