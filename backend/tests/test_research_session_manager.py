from backend.session import (

    InMemoryResearchSessionStore,

    ResearchSessionManager,
)

from frontend.src.workspace import (
    VisualResearchWorkspace,
)


def test_manager_saves_workspace():

    store = (
        InMemoryResearchSessionStore()
    )

    manager = (
        ResearchSessionManager(
            store
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    saved = manager.save_workspace(

        session_id="session-1",

        workspace=workspace,

        paper_title="Example Paper",
    )

    assert (

        saved.session_id

        == "session-1"
    )

    assert (

        len(
            manager.list_sessions()
        )

        == 1
    )


def test_manager_loads_and_deletes_session():

    store = (
        InMemoryResearchSessionStore()
    )

    manager = (
        ResearchSessionManager(
            store
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    manager.save_workspace(

        session_id="session-1",

        workspace=workspace,

        paper_title="Example Paper",
    )

    loaded = manager.load_session(
        "session-1"
    )

    assert (

        loaded.paper_title

        == "Example Paper"
    )

    deleted = manager.delete_session(
        "session-1"
    )

    assert deleted is True

    assert (

        manager.load_session(
            "session-1"
        )

        is None
    )
