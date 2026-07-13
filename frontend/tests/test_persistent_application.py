from backend.session import (
    ResearchCheckpointReason,
)

from frontend.src.persistent_app import (
    create_persistent_application,
)


def test_research_state_survives_application_recreation(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        session_id="session-1",

        paper_id="paper-1",

        paper_title=(
            "Example Paper"
        ),
    )

    artifact = (

        first_app
        .save_interaction_artifact(

            interaction_id=(
                "interaction-1"
            ),

            session_id=(
                "session-1"
            ),

            object_id="attention",

            action="explain",

            content=(

                "Persistent "
                "attention explanation"
            ),
        )
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    session = (

        second_app
        .get_research_session(

            "session-1"
        )
    )

    restored_artifact = (

        second_app
        .artifact_manager
        .get(

            artifact.id
        )
    )

    links = (

        second_app
        .interaction_artifact_correlations
        .links_for_interaction(

            "interaction-1"
        )
    )

    assert session is not None

    assert (

        artifact.id

        in session.artifact_ids
    )

    assert (

        restored_artifact

        is not None
    )

    assert (

        restored_artifact.content

        == (
            "Persistent "
            "attention explanation"
        )
    )

    assert len(links) == 1

    assert (

        links[0].artifact_id

        == artifact.id
    )


def test_checkpoint_history_survives_application_recreation(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        session_id="session-1",

        paper_id="paper-1",

        paper_title=(
            "Example Paper"
        ),
    )

    first_app.checkpoint_workflow_progress(

        "step-1"
    )

    first_app.checkpoint_section(

        "section-2"
    )

    first_app.checkpoint_before_background()

    first_checkpoints = (

        first_app
        .research_checkpoints(

            "session-1"
        )
    )

    assert (

        len(
            first_checkpoints
        )

        == 3
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    restored_checkpoints = (

        second_app
        .research_checkpoints(

            "session-1"
        )
    )

    assert (

        len(
            restored_checkpoints
        )

        == 3
    )

    assert (

        [
            checkpoint.reason

            for checkpoint

            in restored_checkpoints
        ]

        == [

            ResearchCheckpointReason
            .WORKFLOW_PROGRESS,

            ResearchCheckpointReason
            .SECTION_CHANGED,

            ResearchCheckpointReason
            .APPLICATION_BACKGROUND,
        ]
    )


def test_checkpoint_timeline_continues_after_restart(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        "session-1"
    )

    first_app.checkpoint_workflow_progress(

        "step-1"
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    second_app.activate_research_session(

        "session-1"
    )

    second_app.checkpoint_workflow_progress(

        "step-2"
    )

    checkpoints = (

        second_app
        .research_checkpoints(

            "session-1"
        )
    )

    assert len(checkpoints) == 2

    assert (

        checkpoints[0]
        .metadata[
            "step_id"
        ]

        == "step-1"
    )

    assert (

        checkpoints[1]
        .metadata[
            "step_id"
        ]

        == "step-2"
    )


def test_checkpoint_versions_survive_application_recreation(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        session_id="session-1",

        paper_title="Version One",
    )

    first_checkpoint = (

        first_app
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    first_app.active_paper_title = (
        "Version Two"
    )

    first_app.checkpoint_workflow_progress(

        "step-2"
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    checkpoint = (

        second_app
        .get_research_checkpoint(

            first_checkpoint.id
        )
    )

    version = (

        second_app
        .research_checkpoint_version(

            checkpoint.id
        )
    )

    assert version is not None

    assert (

        version.snapshot
        .paper_title

        == "Version One"
    )


def test_recovery_survives_application_recreation(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        session_id="session-1",

        paper_title="State A",
    )

    checkpoint_a = (

        first_app
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    first_app.active_paper_title = (
        "State B"
    )

    first_app.checkpoint_workflow_progress(

        "step-b"
    )

    first_app.restore_research_checkpoint(

        checkpoint_a.id
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    restored_session = (

        second_app
        .get_research_session(

            "session-1"
        )
    )

    assert restored_session is not None

    assert (

        restored_session.paper_title

        == "State A"
    )


def test_recovery_keeps_pre_recovery_history_after_restart(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        session_id="session-1",

        paper_title="State A",
    )

    checkpoint_a = (

        first_app
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    first_app.active_paper_title = (
        "State B"
    )

    checkpoint_b = (

        first_app
        .checkpoint_workflow_progress(

            "step-b"
        )
    )

    result = (

        first_app
        .restore_research_checkpoint(

            checkpoint_a.id
        )
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    assert (

        second_app
        .get_research_checkpoint(

            checkpoint_a.id
        )

        is not None
    )

    assert (

        second_app
        .get_research_checkpoint(

            checkpoint_b.id
        )

        is not None
    )

    assert (

        second_app
        .get_research_checkpoint(

            result
            .safety_checkpoint_id
        )

        is not None
    )

    assert (

        second_app
        .get_research_checkpoint(

            result
            .recovery_checkpoint_id
        )

        is not None
    )


def test_recovery_preview_works_after_application_recreation(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        session_id="session-1",

        paper_title="Historical State",
    )

    checkpoint = (

        first_app
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    first_app.active_paper_title = (
        "Current State"
    )

    first_app.checkpoint_workflow_progress(

        "step-2"
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    second_app.activate_research_session(

        session_id="session-1",

        paper_title="Current State",
    )

    preview = (

        second_app
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


def test_checkpoint_annotations_survive_application_recreation(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        "session-1"
    )

    checkpoint = (

        first_app
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    first_app.update_research_checkpoint_annotation(

        checkpoint.id,

        label=(
            "Best stable state"
        ),

        note=(
            "Return here before "
            "rewriting methodology."
        ),

        pinned=True,
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    annotation = (

        second_app
        .research_checkpoint_annotation(

            checkpoint.id
        )
    )

    assert annotation is not None

    assert (

        annotation.label

        == "Best stable state"
    )

    assert (

        annotation.note

        == (
            "Return here before "
            "rewriting methodology."
        )
    )

    assert annotation.pinned is True


def test_research_history_query_works_after_restart(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        "session-1"
    )

    checkpoint = (

        first_app
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    first_app.update_research_checkpoint_annotation(

        checkpoint.id,

        label=(
            "Stable methodology state"
        ),

        note=(
            "Important recovery point"
        ),

        pinned=True,
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    page = (

        second_app
        .query_research_history(

            session_id=(
                "session-1"
            ),

            pinned=True,

            search="methodology",
        )
    )

    assert page.total == 1

    assert (

        page.items[0].id

        == checkpoint.id
    )


def test_branched_session_survives_application_recreation(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    first_app = (

        create_persistent_application(

            data_directory
        )
    )

    first_app.activate_research_session(

        session_id="session-main",

        paper_title="Historical State",
    )

    checkpoint = (

        first_app
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    first_app.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id=(
            "session-branch"
        ),
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    branch_session = (

        second_app
        .get_research_session(

            "session-branch"
        )
    )

    origin = (

        second_app
        .research_session_branch_origin(

            "session-branch"
        )
    )

    assert branch_session is not None

    assert origin is not None

    assert (

        origin.source_checkpoint_id

        == checkpoint.id
    )
