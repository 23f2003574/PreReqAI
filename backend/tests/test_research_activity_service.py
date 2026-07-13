from datetime import (
    datetime,
    timedelta,
    timezone,
)

from backend.session import (
    InMemoryResearchActivityStore,
    ResearchActivityRecorder,
    ResearchActivityService,
    ResearchActivityType,
)


def create_activity_service_with_events(

    count=3,

):

    store = (
        InMemoryResearchActivityStore()
    )

    base_time = datetime(

        2026,
        7,
        13,
        12,
        0,

        tzinfo=(
            timezone.utc
        ),
    )

    for index in range(count):

        recorder = (

            ResearchActivityRecorder(

                activity_store=store,

                clock=(

                    lambda index=index: (

                        base_time

                        + timedelta(
                            minutes=index
                        )
                    )
                ),

                id_factory=(

                    lambda index=index: (

                        f"event-{index + 1}"
                    )
                ),
            )
        )

        recorder.record(

            ResearchActivityType
            .SESSION_CREATED,

            session_id=(

                f"session-{index + 1}"
            ),
        )

    return (

        ResearchActivityService(

            activity_store=store
        )
    )


def test_activity_timeline_is_newest_first():

    service = (
        create_activity_service_with_events()
    )

    page = (

        service
        .recent_activity()
    )

    assert [

        event.id

        for event

        in page.items

    ] == [

        "event-3",
        "event-2",
        "event-1",
    ]


def test_branch_event_appears_in_parent_and_child_timelines():

    store = (
        InMemoryResearchActivityStore()
    )

    recorder = (

        ResearchActivityRecorder(

            activity_store=(
                store
            )
        )
    )

    recorder.record(

        ResearchActivityType
        .BRANCH_CREATED,

        session_id=(
            "session-parent"
        ),

        related_session_id=(
            "session-child"
        ),
    )

    service = (

        ResearchActivityService(

            activity_store=(
                store
            )
        )
    )

    parent_page = (

        service
        .timeline_for_session(

            "session-parent"
        )
    )

    child_page = (

        service
        .timeline_for_session(

            "session-child"
        )
    )

    assert parent_page.total == 1

    assert child_page.total == 1


def test_activity_timeline_supports_pagination():

    service = (
        create_activity_service_with_events(
            count=25
        )
    )

    page = (

        service
        .recent_activity(

            page=2,

            page_size=10,
        )
    )

    assert len(
        page.items
    ) == 10

    assert page.total == 25

    assert page.has_previous is True

    assert page.has_next is True
