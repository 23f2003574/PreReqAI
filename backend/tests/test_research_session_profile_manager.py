import pytest

from backend.session import (
    ResearchSessionStatus,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def test_updates_session_profile_without_changing_created_time():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    first = (

        application
        .update_research_session_profile(

            "session-a",

            display_name=(
                "Initial Name"
            ),
        )
    )

    second = (

        application
        .update_research_session_profile(

            "session-a",

            display_name=(
                "Updated Name"
            ),
        )
    )

    assert (

        second.display_name

        == "Updated Name"
    )

    assert (

        second.created_at

        == first.created_at
    )

    assert (

        second.updated_at

        >= first.updated_at
    )


def test_can_clear_optional_profile_fields():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.update_research_session_profile(

        "session-a",

        display_name=(
            "Temporary Name"
        ),

        description=(
            "Temporary Description"
        ),
    )

    updated = (

        application
        .update_research_session_profile(

            "session-a",

            display_name=None,

            description=None,
        )
    )

    assert (

        updated.display_name

        is None
    )

    assert (

        updated.description

        is None
    )


def test_manages_session_lifecycle_status():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    paused = (

        application
        .pause_research_session(

            "session-a"
        )
    )

    assert (

        paused.status

        == (
            ResearchSessionStatus
            .PAUSED
        )
    )

    resumed = (

        application
        .resume_research_session(

            "session-a"
        )
    )

    assert (

        resumed.status

        == (
            ResearchSessionStatus
            .ACTIVE
        )
    )

    completed = (

        application
        .complete_research_session(

            "session-a"
        )
    )

    assert (

        completed.status

        == (
            ResearchSessionStatus
            .COMPLETED
        )
    )


def test_archiving_does_not_change_session_status():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.complete_research_session(

        "session-a"
    )

    archived = (

        application
        .archive_research_session(

            "session-a"
        )
    )

    assert (

        archived.status

        == (
            ResearchSessionStatus
            .COMPLETED
        )
    )

    assert archived.archived is True


def test_branch_can_receive_human_readable_profile():

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

    result = (

        application
        .branch_research_checkpoint(

            checkpoint_id=(
                checkpoint.id
            ),

            branch_session_id=(
                "session-math"
            ),

            display_name=(
                "Mathematical Approach"
            ),

            description=(

                "Explore theorem-first "
                "prerequisites."
            ),
        )
    )

    profile = result[
        "profile"
    ]

    assert (

        profile.display_name

        == "Mathematical Approach"
    )

    assert (

        application
        .research_session_display_name(

            "session-math"
        )

        == "Mathematical Approach"
    )


def test_profile_updates_do_not_modify_branch_origin():

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

        display_name=(
            "Initial Branch Name"
        ),
    )

    original_origin = (

        application
        .research_session_branch_origin(

            "session-branch"
        )
    )

    application.update_research_session_profile(

        "session-branch",

        display_name=(
            "Renamed Branch"
        ),

        description=(
            "Updated description"
        ),
    )

    current_origin = (

        application
        .research_session_branch_origin(

            "session-branch"
        )
    )

    assert (

        current_origin.id

        == original_origin.id
    )

    assert (

        current_origin.source_session_id

        == original_origin
        .source_session_id
    )

    assert (

        current_origin.source_checkpoint_id

        == original_origin
        .source_checkpoint_id
    )

    assert (

        current_origin.source_version_id

        == original_origin
        .source_version_id
    )


def test_display_name_falls_back_to_paper_title():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-a",

        paper_title=(
            "Attention Is All You Need"
        ),
    )

    application.save_research_session(

        "session-a",

        paper_title=(
            "Attention Is All You Need"
        ),
    )

    assert (

        application
        .research_session_display_name(

            "session-a"
        )

        == (
            "Attention Is All You Need"
        )
    )


def test_display_name_falls_back_to_session_id():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    assert (

        application
        .research_session_display_name(

            "session-a"
        )

        == "session-a"
    )


def test_cannot_create_profile_for_missing_session():

    application = (
        PreReqAIApplication()
    )

    with pytest.raises(

        ValueError,

        match="does not exist",
    ):

        application.update_research_session_profile(

            "missing-session",

            display_name=(
                "Ghost Branch"
            ),
        )


def test_lineage_tree_contains_human_readable_profiles():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-main"
    )

    application.save_research_session(
        "session-main"
    )

    application.update_research_session_profile(

        "session-main",

        display_name=(
            "Main Research"
        ),
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
            "session-math"
        ),

        display_name=(
            "Mathematical Approach"
        ),
    )

    tree = (

        application
        .research_session_lineage_tree(

            "session-math"
        )
    )

    assert (

        tree.display_name

        == "Main Research"
    )

    assert (

        tree.children[0]
        .display_name

        == "Mathematical Approach"
    )
