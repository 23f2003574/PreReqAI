from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    InMemoryResearchActivityStore,
    ResearchActivityRecorder,
    ResearchActivityType,
)


def test_activity_recorder_uses_injected_clock_and_id():

    occurred_at = datetime(

        2026,
        7,
        13,
        15,
        0,

        tzinfo=(
            timezone.utc
        ),
    )

    store = (
        InMemoryResearchActivityStore()
    )

    recorder = (

        ResearchActivityRecorder(

            activity_store=(
                store
            ),

            clock=lambda: (
                occurred_at
            ),

            id_factory=lambda: (
                "event-fixed"
            ),
        )
    )

    event = recorder.record(

        ResearchActivityType
        .SESSION_CREATED,

        session_id=(
            "session-a"
        ),
    )

    assert event.id == (
        "event-fixed"
    )

    assert event.occurred_at == (
        occurred_at
    )

    assert (

        store.get(
            "event-fixed"
        )

        is not None
    )
