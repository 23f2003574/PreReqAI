import pytest

from backend.session import (
    ResearchActivityType,
    ResearchCheckpointReason,
    ResearchSessionStatus,
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


def test_lineage_traversal_survives_application_recreation(

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

        "session-a"
    )

    checkpoint_a = (

        first_app
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    first_app.branch_research_checkpoint(

        checkpoint_a.id,

        branch_session_id=(
            "session-b"
        ),
    )

    first_app.activate_research_session(

        "session-b"
    )

    checkpoint_b = (

        first_app
        .checkpoint_workflow_progress(

            "step-b"
        )
    )

    first_app.branch_research_checkpoint(

        checkpoint_b.id,

        branch_session_id=(
            "session-c"
        ),
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    assert (

        second_app
        .research_session_root(

            "session-c"
        )

        == "session-a"
    )

    assert (

        second_app
        .research_session_path_from_root(

            "session-c"
        )
        .session_ids

        == [

            "session-a",

            "session-b",

            "session-c",
        ]
    )


def test_branch_profile_survives_application_recreation(

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

        "session-main"
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

    first_app.pause_research_session(

        "session-math"
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    profile = (

        second_app
        .research_session_profile(

            "session-math"
        )
    )

    assert profile is not None

    assert (

        profile.display_name

        == "Mathematical Approach"
    )

    assert (

        profile.status

        == (
            ResearchSessionStatus
            .PAUSED
        )
    )


def test_session_discovery_query_works_after_restart(

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

        paper_title=(
            "Transformer Paper"
        ),
    )

    first_app.save_research_session(

        "session-main",

        paper_title=(
            "Transformer Paper"
        ),
    )

    first_app.update_research_session_profile(

        "session-main",

        display_name=(
            "Transformer Research"
        ),
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
            "math-branch"
        ),

        display_name=(
            "Mathematical Approach"
        ),
    )

    first_app.pause_research_session(

        "math-branch"
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    page = (

        second_app
        .query_research_sessions(

            search="mathematical",

            statuses={
                "paused"
            },

            kinds={
                "branch"
            },
        )
    )

    assert page.total == 1

    assert (

        page.items[0]
        .session_id

        == "math-branch"
    )


def test_session_comparison_reconstructs_after_restart(

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

        "session-main"
    )

    checkpoint = (

        first_app
        .checkpoint_workflow_progress(

            "root-step"
        )
    )

    first_app.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id=(
            "session-a"
        ),
    )

    first_app.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id=(
            "session-b"
        ),
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    comparison = (

        second_app
        .compare_research_sessions(

            "session-a",

            "session-b",
        )
    )

    assert (

        comparison.relationship.value

        == "sibling"
    )

    assert (

        comparison
        .common_ancestor_session_id

        == "session-main"
    )

    assert comparison.lineage_distance == 2


def test_workspace_organization_survives_restart(

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

        "session-a"
    )

    first_app.save_research_session(
        "session-a"
    )

    first_app.tag_research_session(

        "session-a",

        "math-heavy",
    )

    collection = (

        first_app
        .create_research_collection(

            "Current Research"
        )
    )

    first_app.add_research_session_to_collection(

        collection.id,

        "session-a",
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    tags = (

        second_app
        .research_session_tags(

            "session-a"
        )
    )

    collections = (

        second_app
        .research_collections_for_session(

            "session-a"
        )
    )

    assert [

        tag.name

        for tag

        in tags

    ] == [

        "math-heavy"
    ]

    assert [

        item.name

        for item

        in collections

    ] == [

        "Current Research"
    ]

    page = (

        second_app
        .query_research_sessions(

            tag_names={
                "math-heavy"
            },

            collection_ids={
                collection.id
            },
        )
    )

    assert page.total == 1


def test_research_activity_survives_restart(

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

        "session-a"
    )

    first_app.save_research_session(
        "session-a"
    )

    first_app.tag_research_session(

        "session-a",

        "math-heavy",
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    page = (

        second_app
        .research_session_activity(

            "session-a"
        )
    )

    activity_types = {

        event.activity_type

        for event

        in page.items
    }

    assert (

        ResearchActivityType
        .SESSION_CREATED

        in activity_types
    )

    assert (

        ResearchActivityType
        .TAG_ASSIGNED

        in activity_types
    )

    created_events = [

        event

        for event

        in page.items

        if (

            event.activity_type

            == (
                ResearchActivityType
                .SESSION_CREATED
            )
        )
    ]

    assert len(created_events) == 1


def test_workspace_insights_survive_restart(

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

        "session-a"
    )

    first_app.save_research_session(
        "session-a"
    )

    first_app.tag_research_session(

        "session-a",

        "transformers",
    )

    collection = (

        first_app
        .create_research_collection(

            "Current Research"
        )
    )

    first_app.add_research_session_to_collection(

        collection.id,

        "session-a",
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    insights = (

        second_app
        .research_workspace_insights()
    )

    assert (

        insights.overview
        .total_sessions

        == 1
    )

    assert (

        insights.top_tags[0]
        .tag_name

        == "transformers"
    )

    assert (

        insights.largest_collections[0]
        .collection_name

        == "Current Research"
    )


def test_persisted_workspace_can_be_exported_after_restart(

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

        "session-a"
    )

    first_app.save_research_session(
        "session-a"
    )

    first_app.tag_research_session(

        "session-a",

        "transformers",
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    snapshot = (

        second_app
        .export_research_workspace()
    )

    result = (

        second_app
        .research_snapshot_validator
        .validate(
            snapshot
        )
    )

    assert result.is_valid is True

    assert (

        len(
            snapshot.sessions
        )

        == 1
    )


def test_failed_import_remains_rolled_back_after_restart(

    tmp_path,

):

    data_directory = (

        tmp_path

        / "prereqai-data"
    )

    source = (

        create_persistent_application(

            tmp_path

            / "prereqai-source"
        )
    )

    source.activate_research_session(
        "session-a"
    )

    source.save_research_session(
        "session-a"
    )

    checkpoint = (

        source
        .checkpoint_workflow_progress(
            "step-a"
        )
    )

    source.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id=(
            "session-b"
        ),
    )

    snapshot = (

        source
        .export_research_workspace()
    )

    application = (

        create_persistent_application(

            data_directory
        )
    )

    def failing_save(

        *args,

        **kwargs,

    ):

        raise RuntimeError(
            "simulated failure"
        )

    application.session_version_store.save = (
        failing_save
    )

    with pytest.raises(
        RuntimeError
    ):

        application.import_research_snapshot(

            snapshot
        )

    restarted = (

        create_persistent_application(

            data_directory
        )
    )

    assert (

        restarted
        .session_manager
        .list_sessions()

        == []
    )

    assert (

        restarted
        .checkpoint_store
        .list_for_session(
            "session-a"
        )

        == []
    )


def test_persisted_workspace_passes_integrity_audit_after_restart(

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
        "session-main"
    )

    first_app.save_research_session(
        "session-main"
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

    first_app.tag_research_session(

        "session-main",

        "transformers",
    )

    second_app = (

        create_persistent_application(

            data_directory
        )
    )

    report = (

        second_app
        .audit_research_workspace()
    )

    assert report.is_healthy is True
