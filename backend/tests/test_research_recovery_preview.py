import pytest

from frontend.src.app import (
    PreReqAIApplication,
)


def test_preview_reports_changes_before_recovery():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-1",

        paper_title="Historical State",
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    application.active_paper_title = (
        "Current State"
    )

    preview = (

        application
        .preview_research_checkpoint_recovery(

            checkpoint.id
        )
    )

    assert preview.has_changes

    assert (

        "paper_title"

        in (
            preview
            .comparison
            .changed_fields()
        )
    )


def test_preview_does_not_create_checkpoint_or_persist_state():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-1",

        paper_title="Historical State",
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    before_checkpoints = (

        application
        .research_checkpoints(

            "session-1"
        )
    )

    before_versions = (

        application
        .research_session_versions(

            "session-1"
        )
    )

    application.active_paper_title = (
        "Unsaved Current State"
    )

    application.preview_research_checkpoint_recovery(

        checkpoint.id
    )

    after_checkpoints = (

        application
        .research_checkpoints(

            "session-1"
        )
    )

    after_versions = (

        application
        .research_session_versions(

            "session-1"
        )
    )

    assert (

        len(
            after_checkpoints
        )

        == len(
            before_checkpoints
        )
    )

    assert (

        len(
            after_versions
        )

        == len(
            before_versions
        )
    )


def test_preview_does_not_prevent_later_recovery():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-1",

        paper_title="State A",
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    application.active_paper_title = (
        "State B"
    )

    preview = (

        application
        .preview_research_checkpoint_recovery(

            checkpoint.id
        )
    )

    assert preview.has_changes

    application.restore_research_checkpoint(

        checkpoint.id
    )

    assert (

        application
        .active_paper_title

        == "State A"
    )


def test_cannot_preview_checkpoint_from_another_session():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-1"
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    application.activate_research_session(

        "session-2"
    )

    with pytest.raises(

        ValueError,

        match=(
            "does not belong"
        ),
    ):

        application.preview_research_checkpoint_recovery(

            checkpoint.id
        )


def test_compares_two_historical_session_versions():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-1",

        paper_title="Version A",
    )

    checkpoint_a = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    application.active_paper_title = (
        "Version B"
    )

    checkpoint_b = (

        application
        .checkpoint_workflow_progress(

            "step-b"
        )
    )

    comparison = (

        application
        .compare_research_session_versions(

            checkpoint_a
            .snapshot_version_id,

            checkpoint_b
            .snapshot_version_id,
        )
    )

    assert comparison.has_changes

    assert (

        "paper_title"

        in comparison.changed_fields()
    )
