from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    JsonResearchActivityStore,
    ResearchActivityEvent,
    ResearchActivityType,
)


def test_activity_events_survive_store_recreation(

    tmp_path,

):

    path = (

        tmp_path

        / "research_activity_events.json"
    )

    first_store = (

        JsonResearchActivityStore(

            path
        )
    )

    event = ResearchActivityEvent(

        id="event-1",

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

    first_store.append(
        event
    )

    second_store = (

        JsonResearchActivityStore(

            path
        )
    )

    restored = (

        second_store.get(
            "event-1"
        )
    )

    assert restored is not None

    assert (

        restored.activity_type

        == (

            ResearchActivityType
            .SESSION_CREATED
        )
    )

    assert (

        second_store.list_all()

        == [
            restored
        ]
    )
