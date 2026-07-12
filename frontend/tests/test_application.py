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
