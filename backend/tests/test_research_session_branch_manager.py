import pytest

from backend.session import (
    ResearchCheckpointReason,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def test_creates_independent_session_from_checkpoint():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-main",

        paper_title="Historical State",
    )

    source_checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    application.active_paper_title = (
        "Current Main State"
    )

    result = (

        application
        .branch_research_checkpoint(

            checkpoint_id=(
                source_checkpoint.id
            ),

            branch_session_id=(
                "session-branch"
            ),
        )
    )

    branch_session = (

        application
        .get_research_session(

            "session-branch"
        )
    )

    assert branch_session is not None

    assert (

        branch_session.paper_title

        == "Historical State"
    )

    assert (

        application.active_session_id

        == "session-main"
    )

    assert (

        application.active_paper_title

        == "Current Main State"
    )

    assert (

        result[
            "branch"
        ]
        .source_checkpoint_id

        == source_checkpoint.id
    )


def test_branching_does_not_modify_source_checkpoint_history():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-main"
    )

    source_checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    source_version_id = (

        source_checkpoint
        .snapshot_version_id
    )

    before = (

        application
        .research_checkpoints(

            "session-main"
        )
    )

    application.branch_research_checkpoint(

        checkpoint_id=(
            source_checkpoint.id
        ),

        branch_session_id=(
            "session-branch"
        ),
    )

    after = (

        application
        .research_checkpoints(

            "session-main"
        )
    )

    assert len(after) == len(before)

    source_version = (

        application
        .get_research_session_version(

            source_version_id
        )
    )

    assert source_version is not None


def test_branch_starts_with_auditable_origin_checkpoint():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-main"
    )

    source = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    result = (

        application
        .branch_research_checkpoint(

            checkpoint_id=(
                source.id
            ),

            branch_session_id=(
                "session-branch"
            ),
        )
    )

    initial = result[
        "initial_checkpoint"
    ]

    assert (

        initial.reason

        == (
            ResearchCheckpointReason
            .SESSION_BRANCHED
        )
    )

    assert (

        initial.metadata[
            "source_checkpoint_id"
        ]

        == source.id
    )

    assert (

        initial.metadata[
            "source_session_id"
        ]

        == "session-main"
    )


def test_can_query_branch_session_origin():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-main"
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    application.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id=(
            "session-branch"
        ),
    )

    origin = (

        application
        .research_session_branch_origin(

            "session-branch"
        )
    )

    assert origin is not None

    assert (

        origin.source_session_id

        == "session-main"
    )

    assert (

        origin.source_checkpoint_id

        == checkpoint.id
    )


def test_checkpoint_can_create_multiple_independent_branches():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-main"
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    application.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id=(
            "branch-a"
        ),
    )

    application.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id=(
            "branch-b"
        ),
    )

    branches = (

        application
        .research_checkpoint_branches(

            checkpoint.id
        )
    )

    assert len(branches) == 2

    assert {

        branch.branch_session_id

        for branch

        in branches

    } == {

        "branch-a",

        "branch-b",
    }


def test_cannot_branch_into_existing_session_id():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-main"
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    application.activate_research_session(

        "existing-session"
    )

    application.save_research_session(

        "existing-session"
    )

    with pytest.raises(

        ValueError,

        match=(
            "already exists"
        ),
    ):

        application.branch_research_checkpoint(

            checkpoint.id,

            branch_session_id=(
                "existing-session"
            ),
        )


def test_branch_and_source_can_evolve_independently():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-main",

        paper_title="State A",
    )

    checkpoint_a = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    application.active_paper_title = (
        "Main State B"
    )

    application.checkpoint_workflow_progress(

        "step-b"
    )

    application.branch_and_activate_research_checkpoint(

        checkpoint_a.id,

        branch_session_id=(
            "session-branch"
        ),
    )

    assert (

        application.active_paper_title

        == "State A"
    )

    application.active_paper_title = (
        "Branch State C"
    )

    application.checkpoint_workflow_progress(

        "branch-step"
    )

    main_session = (

        application
        .get_research_session(

            "session-main"
        )
    )

    branch_session = (

        application
        .get_research_session(

            "session-branch"
        )
    )

    assert (

        main_session.paper_title

        == "Main State B"
    )

    assert (

        branch_session.paper_title

        == "Branch State C"
    )


def test_application_traverses_real_branch_lineage():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    checkpoint_a = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    application.branch_research_checkpoint(

        checkpoint_a.id,

        branch_session_id=(
            "session-b"
        ),
    )

    application.activate_research_session(

        "session-b"
    )

    checkpoint_b = (

        application
        .checkpoint_workflow_progress(

            "step-b"
        )
    )

    application.branch_research_checkpoint(

        checkpoint_b.id,

        branch_session_id=(
            "session-c"
        ),
    )

    assert (

        application
        .research_session_root(

            "session-c"
        )

        == "session-a"
    )

    assert (

        application
        .research_session_ancestors(

            "session-c"
        )

        == [
            "session-b",
            "session-a",
        ]
    )

    assert (

        application
        .research_session_depth(

            "session-c"
        )

        == 2
    )
