from backend.session import (
    ResearchSnapshotImportStrategy,
    ResearchWorkspaceChangeOperation,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def create_complex_workspace():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "root"
    )

    application.save_research_session(
        "root"
    )

    application.update_research_session_profile(

        "root",

        display_name="Root",
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(
            "s1"
        )
    )

    application.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id="math",

        display_name=(
            "Mathematical Route"
        ),
    )

    application.tag_research_session(

        "root",

        "transformers",
    )

    collection = (

        application
        .create_research_collection(

            "Current Research"
        )
    )

    application.add_research_session_to_collection(

        collection.id,

        "root",
    )

    return application


def test_creating_session_emits_workspace_change():

    application = (
        PreReqAIApplication()
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    application.activate_research_session(
        "session-a"
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    assert any(

        event.entity_type == "session"

        and event.entity_id
        == "session-a"

        and event.operation
        == (

            ResearchWorkspaceChangeOperation
            .CREATED
        )

        for event in page.events
    )


def test_reactivating_existing_session_emits_no_new_session_event():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    application.activate_research_session(
        "session-a"
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    assert not any(

        event.entity_type == "session"

        and event.operation
        == (

            ResearchWorkspaceChangeOperation
            .CREATED
        )

        for event in page.events
    )


def test_checkpoint_creation_emits_workspace_change():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(
            "step-1"
        )
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    matching = [

        event

        for event in page.events

        if event.entity_type
        == "checkpoint"
    ]

    assert len(matching) == 1

    assert (

        matching[0].entity_id

        == checkpoint.id
    )

    assert (

        matching[0]
        .related_entity_ids

        == ["session-a"]
    )


def test_branch_creation_emits_session_and_branch_events():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    checkpoint = (

        application
        .checkpoint_workflow_progress(
            "step-1"
        )
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    application.branch_research_checkpoint(

        checkpoint.id,

        branch_session_id="branch-a",
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    session_events = [

        event

        for event in page.events

        if event.entity_type
        == "session"
    ]

    branch_events = [

        event

        for event in page.events

        if event.entity_type
        == "branch"
    ]

    assert len(session_events) == 1

    assert (

        session_events[0].entity_id

        == "branch-a"
    )

    assert len(branch_events) == 1

    assert (

        branch_events[0]
        .related_entity_ids

        == [

            "session-a",

            "branch-a",
        ]
    )


def test_tag_assignment_emits_workspace_change_only_once():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    tag = (

        application
        .tag_research_session(

            "session-a",

            "transformers",
        )
    )

    application.tag_research_session(

        "session-a",

        "transformers",
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    tag_events = [

        event

        for event in page.events

        if event.entity_type
        == "tag_assignment"
    ]

    assert len(tag_events) == 1

    assert (

        tag_events[0]
        .related_entity_ids

        == [

            "session-a",

            tag.id,
        ]
    )


def test_untagging_session_emits_deleted_change():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.tag_research_session(

        "session-a",

        "transformers",
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    application.untag_research_session(

        "session-a",

        "transformers",
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    tag_events = [

        event

        for event in page.events

        if event.entity_type
        == "tag_assignment"
    ]

    assert len(tag_events) == 1

    assert (

        tag_events[0].operation

        == ResearchWorkspaceChangeOperation
        .DELETED
    )


def test_collection_membership_emits_created_and_deleted_changes():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    collection = (

        application
        .create_research_collection(
            "Research"
        )
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    application.add_research_session_to_collection(

        collection.id,

        "session-a",
    )

    application.remove_research_session_from_collection(

        collection.id,

        "session-a",
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    membership_events = [

        event

        for event in page.events

        if event.entity_type
        == "collection_membership"
    ]

    assert (

        [
            event.operation

            for event in membership_events
        ]

        == [

            ResearchWorkspaceChangeOperation
            .CREATED,

            ResearchWorkspaceChangeOperation
            .DELETED,
        ]
    )


def test_lifecycle_change_emits_previous_and_current_state():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    application.pause_research_session(
        "session-a"
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    lifecycle_events = [

        event

        for event in page.events

        if event.metadata.get("change")
        == "lifecycle_state"
    ]

    assert len(lifecycle_events) == 1

    assert (

        lifecycle_events[0].metadata[
            "previous_state"
        ]

        == "active"
    )

    assert (

        lifecycle_events[0].metadata[
            "current_state"
        ]

        == "paused"
    )


def test_profile_update_emits_workspace_change():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    application.update_research_session_profile(

        "session-a",

        display_name="Renamed",
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    matching = [

        event

        for event in page.events

        if event.entity_type
        == "session_profile"
    ]

    assert len(matching) == 1

    assert (

        matching[0].entity_id

        == "session-a"
    )


def test_snapshot_import_emits_one_summary_change_event():

    source = create_complex_workspace()

    snapshot = (

        source
        .export_research_workspace()
    )

    target = (
        PreReqAIApplication()
    )

    before = (

        target
        .get_latest_research_workspace_change_sequence()
    )

    result = (

        target
        .import_research_snapshot(

            snapshot
        )
    )

    page = (

        target
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    imported_events = [

        event

        for event in page.events

        if event.operation
        == (

            ResearchWorkspaceChangeOperation
            .IMPORTED
        )
    ]

    assert len(imported_events) == 1

    assert (

        imported_events[0].entity_id

        == result.snapshot_id
    )

    assert (

        imported_events[0]
        .metadata[
            "imported_sessions"
        ]

        == result.imported_sessions
    )


def test_failed_snapshot_import_emits_no_change_event():

    target = (
        PreReqAIApplication()
    )

    snapshot = (

        create_complex_workspace()
        .export_research_workspace()
    )

    def failing_save(

        *args,

        **kwargs,

    ):

        raise RuntimeError(
            "simulated failure"
        )

    target.session_version_store.save = (
        failing_save
    )

    before = (

        target
        .get_latest_research_workspace_change_sequence()
    )

    try:

        target.import_research_snapshot(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REMAP_ALL
            ),
        )

    except RuntimeError:

        pass

    page = (

        target
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    assert page.events == []


def test_workspace_audit_emits_no_change_events():

    application = create_complex_workspace()

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    application.audit_research_workspace()

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    assert page.events == []


def test_repair_planning_emits_no_change_events():

    application = create_complex_workspace()

    report = (

        application
        .audit_research_workspace()
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    application.plan_research_workspace_repairs(
        report
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    assert page.events == []


def test_export_and_preview_emit_no_change_events():

    application = create_complex_workspace()

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    snapshot = (

        application
        .export_research_workspace()
    )

    application.preview_research_snapshot_import(
        snapshot
    )

    application.query_research_sessions(
        search="root"
    )

    application.compare_research_sessions(
        "root",

        "math",
    )

    application.research_workspace_insights()

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    assert page.events == []


def test_low_level_store_mutation_emits_no_change_event():

    application = (
        PreReqAIApplication()
    )

    application.session_manager.save_workspace(

        session_id="orphan",

        workspace=(
            application.workspace
        ),
    )

    before = (

        application
        .get_latest_research_workspace_change_sequence()
    )

    application.session_profile_manager.create(
        session_id="orphan"
    )

    page = (

        application
        .get_research_workspace_changes(

            after_sequence=before
        )
    )

    assert page.events == []
