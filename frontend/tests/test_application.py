from backend.interaction.interaction_history import (
    InteractionHistory,
)

from backend.interaction.object_action import (
    ObjectAction,
)

from backend.interaction.research_object import (
    ResearchObject,
)

from backend.interaction.research_object_type import (
    ResearchObjectType,
)

from backend.session import (
    ResearchCheckpointReason,
)

from frontend.src import (
    PreReqAIApplication,
)

from frontend.src.workspace import (
    VisualResearchWorkspace,
)


def test_application_creates_workspace():

    application = (
        PreReqAIApplication()
    )

    assert isinstance(

        application.workspace,

        VisualResearchWorkspace,
    )


def test_application_saves_and_loads_research_session():

    application = (
        PreReqAIApplication()
    )

    saved = (

        application
        .save_research_session(

            session_id="session-1",

            paper_id="paper-1",

            paper_title=(
                "Example Paper"
            ),
        )
    )

    assert (

        saved.session_id

        == "session-1"
    )

    loaded = (

        application
        .get_research_session(
            "session-1"
        )
    )

    assert (

        loaded.paper_title

        == "Example Paper"
    )

    assert (

        len(
            application
            .research_sessions()
        )

        == 1
    )


def test_application_restores_selected_object_after_restart():

    application = (
        PreReqAIApplication()
    )

    research_object = ResearchObject(

        id="attention",

        object_type=(
            ResearchObjectType.CONCEPT
        ),

        title="Attention",

        description=(
            "Attention mechanism"
        ),
    )

    application.workspace.inspect_object(

        research_object
    )

    application.save_research_session(

        session_id="session-1",

        paper_title="Example Paper",
    )

    application.workspace.state.selected_object = None

    application.register_research_objects(
        [research_object]
    )

    result = (

        application
        .restore_research_session(
            "session-1"
        )
    )

    assert (

        result.restored_object

        is research_object
    )

    assert (

        application.workspace.state
        .selected_object

        is research_object
    )


def test_application_saves_learning_artifact_and_references_it_in_session():

    application = (
        PreReqAIApplication()
    )

    artifact = (

        application
        .save_learning_artifact(

            session_id="session-1",

            object_id="attention",

            action="explain",

            content=(
                "Attention explanation"
            ),
        )
    )

    assert artifact.version == 1

    assert (

        len(

            application
            .research_artifacts(
                "session-1"
            )
        )

        == 1
    )

    assert (

        len(

            application
            .research_artifacts_for_object(
                "session-1",

                "attention",
            )
        )

        == 1
    )

    saved = (

        application
        .save_research_session(

            session_id="session-1",

            paper_title=(
                "Example Paper"
            ),
        )
    )

    assert (

        saved.artifact_ids

        == [
            artifact.id
        ]
    )


def test_application_correlates_interaction_with_exact_artifact():

    application = (
        PreReqAIApplication()
    )

    class Session:

        interaction_history = (
            InteractionHistory()
        )

    Session.interaction_history.record(

        "attention",

        "Attention",

        ObjectAction.EXPLAIN,
    )

    application.workspace.workspace.load_interaction_history(

        Session()
    )

    entry = (

        application
        .workspace
        .history()[0]
    )

    assert entry.artifact_ids == []

    artifact = (

        application
        .save_interaction_artifact(

            interaction_id=entry.id,

            session_id="session-1",

            object_id="attention",

            action=ObjectAction.EXPLAIN,

            content="Attention explanation",
        )
    )

    application.workspace.workspace.load_interaction_history(

        Session()
    )

    refreshed_entry = (

        application
        .workspace
        .history()[0]
    )

    assert (

        refreshed_entry.artifact_ids

        == [
            artifact.id
        ]
    )


def test_application_restores_exact_interaction_artifact():

    application = (
        PreReqAIApplication()
    )

    artifact = (

        application
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
                "Exact historical "
                "explanation"
            ),
        )
    )

    result = (

        application
        .restore_interaction_artifacts(

            "interaction-1"
        )
    )

    assert result.restored is True

    assert (

        result.artifacts[0].id

        == artifact.id
    )

    assert (

        application
        .workspace
        .learning_content()
        .body

        == (
            "Exact historical "
            "explanation"
        )
    )


def test_application_restores_history_entry_by_clicking_it():

    application = (
        PreReqAIApplication()
    )

    class Session:

        interaction_history = (
            InteractionHistory()
        )

    Session.interaction_history.record(

        "attention",

        "Attention",

        ObjectAction.EXPLAIN,
    )

    application.workspace.workspace.load_interaction_history(

        Session()
    )

    entry = (

        application
        .workspace
        .history()[0]
    )

    artifact = (

        application
        .save_interaction_artifact(

            interaction_id=entry.id,

            session_id="session-1",

            object_id="attention",

            action=ObjectAction.EXPLAIN,

            content="Explanation v1",
        )
    )

    application.workspace.workspace.load_interaction_history(

        Session()
    )

    refreshed_entry = (

        application
        .workspace
        .history()[0]
    )

    result = (

        application
        .restore_history_entry(

            refreshed_entry.id
        )
    )

    assert result.restored is True

    assert (

        result.artifacts[0].id

        == artifact.id
    )

    assert (

        application
        .workspace
        .learning_content()
        .body

        == "Explanation v1"
    )


def test_application_restore_history_entry_handles_unknown_entry():

    application = (
        PreReqAIApplication()
    )

    result = (

        application
        .restore_history_entry(

            "unknown-entry"
        )
    )

    assert result.restored is False


def test_artifact_creation_checkpoints_active_session():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-1",

        paper_id="paper-1",

        paper_title="Example Paper",
    )

    application.save_interaction_artifact(

        interaction_id="interaction-1",

        session_id="session-1",

        object_id="attention",

        action="explain",

        content="Attention explanation",
    )

    snapshot = (

        application
        .get_research_session(

            "session-1"
        )
    )

    assert snapshot is not None

    assert (

        len(
            snapshot.artifact_ids
        )

        == 1
    )

    checkpoint = (

        application
        .latest_research_checkpoint(

            "session-1"
        )
    )

    assert checkpoint is not None

    assert (

        checkpoint.reason

        == (
            ResearchCheckpointReason
            .ARTIFACT_CREATED
        )
    )


def test_checkpoint_without_active_session_is_safe():

    application = (
        PreReqAIApplication()
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    assert checkpoint is None


def test_manual_checkpoint_uses_same_pipeline_as_autosave():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-1",

        paper_title="Example Paper",
    )

    checkpoint = (

        application
        .checkpoint_research_session()
    )

    assert checkpoint is not None

    assert (

        checkpoint.reason

        == (
            ResearchCheckpointReason
            .MANUAL
        )
    )

    assert (

        application
        .get_research_session(
            "session-1"
        )

        is not None
    )

    deactivated = (

        application
        .deactivate_research_session()
    )

    assert deactivated == "session-1"

    assert (

        application
        .checkpoint_research_session()

        is None
    )


def test_checkpoints_preserve_distinct_historical_snapshots():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-1"
    )

    application.active_paper_title = (
        "Version One"
    )

    first_checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    application.active_paper_title = (
        "Version Two"
    )

    second_checkpoint = (

        application
        .checkpoint_workflow_progress(

            "step-2"
        )
    )

    first_version = (

        application
        .research_checkpoint_version(

            first_checkpoint.id
        )
    )

    second_version = (

        application
        .research_checkpoint_version(

            second_checkpoint.id
        )
    )

    assert (

        first_version
        .snapshot
        .paper_title

        == "Version One"
    )

    assert (

        second_version
        .snapshot
        .paper_title

        == "Version Two"
    )


def test_application_exposes_annotated_checkpoint_timeline():

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

    application.update_research_checkpoint_annotation(

        checkpoint.id,

        label=(
            "Stable workflow state"
        ),

        pinned=True,
    )

    timeline = (

        application
        .annotated_research_checkpoints(

            "session-1"
        )
    )

    assert len(timeline) == 1

    assert (

        timeline[0].label

        == "Stable workflow state"
    )

    assert timeline[0].pinned is True


def test_application_lists_only_pinned_checkpoints():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-1"
    )

    first = (

        application
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    second = (

        application
        .checkpoint_workflow_progress(

            "step-2"
        )
    )

    application.pin_research_checkpoint(

        second.id
    )

    pinned = (

        application
        .pinned_research_checkpoints(

            "session-1"
        )
    )

    assert len(pinned) == 1

    assert (

        pinned[0]
        .checkpoint
        .id

        == second.id
    )

    assert (

        pinned[0]
        .checkpoint
        .id

        != first.id
    )


def test_annotation_updates_do_not_modify_historical_version():

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

    version_before = (

        application
        .research_checkpoint_version(

            checkpoint.id
        )
    )

    application.update_research_checkpoint_annotation(

        checkpoint.id,

        label="Renamed checkpoint",

        note="Human-authored note",

        pinned=True,
    )

    version_after = (

        application
        .research_checkpoint_version(

            checkpoint.id
        )
    )

    assert (

        version_after.id

        == version_before.id
    )

    assert (

        version_after.snapshot
        .paper_title

        == "Historical State"
    )


def test_removing_annotation_does_not_delete_checkpoint():

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

    application.label_research_checkpoint(

        checkpoint.id,

        "Temporary label",
    )

    removed = (

        application
        .remove_research_checkpoint_annotation(

            checkpoint.id
        )
    )

    assert removed is True

    assert (

        application
        .research_checkpoint_annotation(

            checkpoint.id
        )

        is None
    )

    assert (

        application
        .get_research_checkpoint(

            checkpoint.id
        )

        is not None
    )


def test_application_queries_pinned_research_history():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-1"
    )

    first = (

        application
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    second = (

        application
        .checkpoint_workflow_progress(

            "step-2"
        )
    )

    application.update_research_checkpoint_annotation(

        second.id,

        label=(
            "Important methodology state"
        ),

        pinned=True,
    )

    page = (

        application
        .query_active_research_history(

            pinned=True,

            search="methodology",
        )
    )

    assert page.total == 1

    assert (

        page.items[0].id

        == second.id
    )

    assert (

        page.items[0].id

        != first.id
    )


def test_history_query_is_read_only():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-1"
    )

    application.checkpoint_workflow_progress(

        "step-1"
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

    application.query_research_history(

        session_id="session-1",

        search="workflow",

        limit=10,
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
