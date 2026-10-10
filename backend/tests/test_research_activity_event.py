from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    ResearchActivityActorType,
    ResearchActivityEvent,
    ResearchActivityType,
)


def test_activity_event_round_trip():

    event = (

        ResearchActivityEvent(

            id="event-1",

            activity_type=(

                ResearchActivityType
                .SESSION_STATUS_CHANGED
            ),

            occurred_at=(

                datetime(

                    2026,
                    7,
                    13,
                    12,
                    30,

                    tzinfo=(
                        timezone.utc
                    ),
                )
            ),

            session_id=(
                "session-a"
            ),

            actor_type=(

                ResearchActivityActorType
                .USER
            ),

            metadata={

                "old_status":
                    "active",

                "new_status":
                    "paused",
            },
        )
    )

    restored = (

        ResearchActivityEvent
        .from_dict(

            event.to_dict()
        )
    )

    assert restored == event
