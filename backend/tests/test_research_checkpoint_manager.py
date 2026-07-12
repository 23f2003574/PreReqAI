from backend.session import (

    InMemoryResearchCheckpointStore,

    InMemoryResearchSessionStore,

    ResearchCheckpointManager,

    ResearchCheckpointPolicy,

    ResearchCheckpointReason,

    ResearchSessionManager,
)

from frontend.src.workspace import (
    VisualResearchWorkspace,
)


def test_creates_research_checkpoint():

    store = (
        InMemoryResearchSessionStore()
    )

    session_manager = (

        ResearchSessionManager(
            store
        )
    )

    checkpoint_manager = (

        ResearchCheckpointManager(

            session_manager=(
                session_manager
            ),

            checkpoint_store=(

                InMemoryResearchCheckpointStore()
            ),
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    checkpoint = (

        checkpoint_manager
        .checkpoint(

            session_id="session-1",

            workspace=workspace,

            reason=(

                ResearchCheckpointReason
                .WORKFLOW_PROGRESS
            ),
        )
    )

    assert checkpoint is not None

    assert (

        checkpoint.session_id

        == "session-1"
    )

    assert (

        store.load(
            "session-1"
        )

        is not None
    )


def test_skips_disabled_checkpoint_reason():

    store = (
        InMemoryResearchSessionStore()
    )

    session_manager = (

        ResearchSessionManager(
            store
        )
    )

    policy = (

        ResearchCheckpointPolicy(

            enabled_reasons=[]
        )
    )

    checkpoint_manager = (

        ResearchCheckpointManager(

            session_manager=(
                session_manager
            ),

            checkpoint_store=(

                InMemoryResearchCheckpointStore()
            ),

            policy=policy,
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    checkpoint = (

        checkpoint_manager
        .checkpoint(

            session_id="session-1",

            workspace=workspace,

            reason=(

                ResearchCheckpointReason
                .WORKFLOW_PROGRESS
            ),
        )
    )

    assert checkpoint is None

    assert (

        store.load(
            "session-1"
        )

        is None
    )


def test_latest_checkpoint_returns_most_recent():

    store = (
        InMemoryResearchSessionStore()
    )

    session_manager = (

        ResearchSessionManager(
            store
        )
    )

    checkpoint_manager = (

        ResearchCheckpointManager(

            session_manager=(
                session_manager
            ),

            checkpoint_store=(

                InMemoryResearchCheckpointStore()
            ),
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    first = (

        checkpoint_manager
        .checkpoint(

            session_id="session-1",

            workspace=workspace,

            reason=(

                ResearchCheckpointReason
                .RESEARCH_OBJECT_CHANGED
            ),
        )
    )

    second = (

        checkpoint_manager
        .checkpoint(

            session_id="session-1",

            workspace=workspace,

            reason=(

                ResearchCheckpointReason
                .ARTIFACT_CREATED
            ),
        )
    )

    assert (

        len(

            checkpoint_manager
            .list_checkpoints(
                "session-1"
            )
        )

        == 2
    )

    latest = (

        checkpoint_manager
        .latest_checkpoint(
            "session-1"
        )
    )

    assert latest.id == second.id

    assert latest.id != first.id


def test_get_and_delete_checkpoint():

    store = (
        InMemoryResearchSessionStore()
    )

    session_manager = (

        ResearchSessionManager(
            store
        )
    )

    checkpoint_manager = (

        ResearchCheckpointManager(

            session_manager=(
                session_manager
            ),

            checkpoint_store=(

                InMemoryResearchCheckpointStore()
            ),
        )
    )

    workspace = (
        VisualResearchWorkspace()
    )

    checkpoint = (

        checkpoint_manager
        .checkpoint(

            session_id="session-1",

            workspace=workspace,

            reason=(

                ResearchCheckpointReason
                .ARTIFACT_CREATED
            ),
        )
    )

    fetched = (

        checkpoint_manager
        .get_checkpoint(

            checkpoint.id
        )
    )

    assert fetched.id == checkpoint.id

    deleted = (

        checkpoint_manager
        .delete_checkpoint(

            checkpoint.id
        )
    )

    assert deleted is True

    assert (

        checkpoint_manager
        .get_checkpoint(

            checkpoint.id
        )

        is None
    )
