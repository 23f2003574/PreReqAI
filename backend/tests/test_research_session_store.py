from backend.session import (

    InMemoryResearchSessionStore,

    ResearchSessionSnapshot,
)


def test_saves_and_loads_session():

    store = (
        InMemoryResearchSessionStore()
    )

    snapshot = (

        ResearchSessionSnapshot(

            session_id="session-1",

            paper_id="paper-1",

            paper_title=(
                "Example Paper"
            ),
        )
    )

    store.save(
        snapshot
    )

    loaded = store.load(
        "session-1"
    )

    assert loaded is not None

    assert (

        loaded.session_id

        == "session-1"
    )

    assert (

        loaded.paper_title

        == "Example Paper"
    )


def test_returns_independent_snapshot():

    store = (
        InMemoryResearchSessionStore()
    )

    snapshot = (

        ResearchSessionSnapshot(

            session_id="session-1",
        )
    )

    store.save(
        snapshot
    )

    loaded = store.load(
        "session-1"
    )

    loaded.active_view = (
        "knowledge_graph"
    )

    stored_again = store.load(
        "session-1"
    )

    assert (

        stored_again.active_view

        == "paper"
    )


def test_deletes_session():

    store = (
        InMemoryResearchSessionStore()
    )

    snapshot = (

        ResearchSessionSnapshot(

            session_id="session-1",
        )
    )

    store.save(
        snapshot
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
