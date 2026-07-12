from backend.session import (

    JsonResearchSessionStore,

    ResearchSessionSnapshot,
)


def test_session_survives_store_recreation(

    tmp_path,

):

    path = (

        tmp_path

        / "sessions.json"
    )

    first_store = (

        JsonResearchSessionStore(
            path
        )
    )

    first_store.save(

        ResearchSessionSnapshot(

            session_id="session-1",

            paper_title=(
                "Example Paper"
            ),
        )
    )

    second_store = (

        JsonResearchSessionStore(
            path
        )
    )

    restored = (

        second_store.load(

            "session-1"
        )
    )

    assert restored is not None

    assert (

        restored.paper_title

        == "Example Paper"
    )


def test_deletes_and_lists_sessions(

    tmp_path,

):

    path = (

        tmp_path

        / "sessions.json"
    )

    store = (

        JsonResearchSessionStore(
            path
        )
    )

    store.save(

        ResearchSessionSnapshot(

            session_id="session-1",
        )
    )

    store.save(

        ResearchSessionSnapshot(

            session_id="session-2",
        )
    )

    assert (

        len(
            store.list_sessions()
        )

        == 2
    )

    deleted = store.delete(
        "session-1"
    )

    assert deleted is True

    assert (

        store.load(
            "session-1"
        )

        is None
    )

    assert (

        len(
            store.list_sessions()
        )

        == 1
    )
