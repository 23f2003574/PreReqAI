from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    InMemoryResearchActivityStore,
    ResearchActivityEvent,
    ResearchActivityType,
)


def _make_event(event_id="event-1"):

    return ResearchActivityEvent(

        id=event_id,

        activity_type=(

            ResearchActivityType
            .SESSION_CREATED
        ),

        occurred_at=(

            datetime(

                2026,
                7,
                13,
                12,
                0,

                tzinfo=(
                    timezone.utc
                ),
            )
        ),

        session_id="session-a",
    )


def test_activity_store_rejects_duplicate_event_ids():

    store = (
        InMemoryResearchActivityStore()
    )

    event = _make_event()

    store.append(
        event
    )

    with pytest.raises(

        ValueError,

        match="already exists",
    ):

        store.append(
            event
        )


def test_activity_store_preserves_append_order():

    store = (
        InMemoryResearchActivityStore()
    )

    store.append(
        _make_event("event-1")
    )

    store.append(
        _make_event("event-2")
    )

    store.append(
        _make_event("event-3")
    )

    assert [

        event.id

        for event

        in store.list_all()

    ] == [

        "event-1",

        "event-2",

        "event-3",
    ]
