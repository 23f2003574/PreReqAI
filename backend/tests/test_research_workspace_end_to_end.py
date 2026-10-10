from backend.session import (
    ResearchSnapshotImportStrategy,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def normalize_snapshot(

    snapshot,

):

    payload = snapshot.to_dict()

    payload["manifest"].pop(
        "snapshot_id"
    )

    payload["manifest"].pop(
        "created_at"
    )

    return payload


def test_complete_research_workspace_lifecycle_through_gateway():

    source_application = (
        PreReqAIApplication()
    )

    workspace = (

        source_application
        .research_workspace
    )

    # Step 1 -- capability discovery.

    assert (

        workspace.supports(
            "sessions"
        )

        is True
    )

    assert (

        workspace.supports(
            "lineage"
        )

        is True
    )

    assert (

        workspace.supports(
            "snapshots"
        )

        is True
    )

    # Step 2 -- remember initial cursor.

    initial_cursor = (

        workspace
        .get_latest_change_sequence()
    )

    # Step 3 -- create root session.

    root = (

        workspace
        .create_session(

            "root",

            paper_title=(

                "How can transformer "
                "reasoning be improved?"
            ),
        )
    )

    # Step 4 -- update profile.

    workspace.update_session_profile(

        root.session_id,

        display_name=(

            "Transformer Reasoning "
            "Research"
        ),

        description=(

            "Investigating mathematical "
            "and implementation-level "
            "routes."
        ),
    )

    # Step 5 -- create checkpoint.

    root_checkpoint = (

        workspace
        .create_checkpoint(

            root.session_id
        )
    )

    assert root_checkpoint is not None

    # Step 6 -- create branches.

    mathematical_result = (

        workspace
        .branch_session(

            root.session_id,

            branch_session_id=(
                "mathematical"
            ),

            display_name=(
                "Mathematical Route"
            ),
        )
    )

    implementation_result = (

        workspace
        .branch_session(

            root.session_id,

            branch_session_id=(
                "implementation"
            ),

            display_name=(
                "Implementation Route"
            ),
        )
    )

    mathematical_checkpoint = (

        mathematical_result[
            "initial_checkpoint"
        ]
    )

    spectral_result = (

        workspace
        .branch_session(

            mathematical_result[
                "branch"
            ]
            .branch_session_id,

            branch_session_id=(
                "spectral"
            ),

            display_name=(
                "Spectral Route"
            ),
        )
    )

    assert (

        mathematical_result["branch"]
        .branch_session_id

        == "mathematical"
    )

    assert (

        implementation_result["branch"]
        .branch_session_id

        == "implementation"
    )

    assert (

        spectral_result["branch"]
        .branch_session_id

        == "spectral"
    )

    # Step 7 -- verify lineage.

    lineage = (

        workspace
        .get_lineage(

            root.session_id
        )
    )

    child_ids = {

        child.session_id

        for child

        in lineage.children
    }

    assert child_ids == {

        "mathematical",

        "implementation",
    }

    mathematical_node = next(

        child

        for child in lineage.children

        if child.session_id
        == "mathematical"
    )

    assert (

        {
            grandchild.session_id

            for grandchild

            in mathematical_node.children
        }

        == {"spectral"}
    )

    # Step 8 -- organize research.

    workspace.create_tag(
        "transformers"
    )

    workspace.assign_tag(

        root.session_id,

        "transformers",
    )

    workspace.assign_tag(

        "mathematical",

        "transformers",
    )

    active_collection = (

        workspace
        .create_collection(

            "Active Research"
        )
    )

    workspace.add_collection_member(

        active_collection.id,

        root.session_id,
    )

    workspace.add_collection_member(

        active_collection.id,

        "mathematical",
    )

    # Step 9 -- compare branches.

    comparison = (

        workspace
        .compare_sessions(

            "mathematical",

            "implementation",
        )
    )

    assert (

        comparison
        .common_ancestor_session_id

        == root.session_id
    )

    assert (

        comparison.relationship.value

        == "sibling"
    )

    # Step 10 -- check insights.

    insights = (

        workspace
        .get_workspace_insights()
    )

    assert (

        insights.overview
        .total_sessions

        >= 4
    )

    assert (

        insights.lineage
        .total_branches

        >= 3
    )

    # Step 11 -- verify change feed.

    changes = (

        workspace
        .get_changes(

            after_sequence=(
                initial_cursor
            )
        )
    )

    assert len(changes.events) > 0

    sequences = [

        event.sequence

        for event in changes.events
    ]

    assert (

        sequences

        == sorted(sequences)
    )

    assert (

        len(sequences)

        == len(
            set(sequences)
        )
    )

    # Step 12 -- audit source workspace.

    source_report = (

        workspace.audit_workspace()
    )

    assert (
        source_report.is_healthy
        is True
    )

    # Step 13 -- export snapshot.

    snapshot = (
        workspace.export_workspace()
    )

    assert len(snapshot.sessions) >= 4

    assert (

        len(snapshot.profiles)

        >= 1
    )

    assert (

        len(snapshot.checkpoints)

        >= 1
    )

    assert (

        len(snapshot.branches)

        >= 3
    )

    assert len(snapshot.tags) >= 1

    assert (

        len(snapshot.collections)

        >= 1
    )

    assert (

        len(snapshot.activity_events)

        > 0
    )

    # Step 14 -- create independent
    # target workspace.

    target_application = (
        PreReqAIApplication()
    )

    target_workspace = (

        target_application
        .research_workspace
    )

    # Step 15 -- preview import.

    preview = (

        target_workspace
        .preview_import(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REJECT
            ),
        )
    )

    assert preview.has_conflicts is False

    # Step 16 -- import.

    result = (

        target_workspace
        .import_snapshot(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REJECT
            ),
        )
    )

    assert result.imported_sessions >= 4

    # Step 17 -- audit imported
    # workspace.

    target_report = (

        target_workspace
        .audit_workspace()
    )

    assert (
        target_report.is_healthy
        is True
    )

    # Step 18 -- verify import change
    # event.

    target_changes = (

        target_workspace
        .get_changes(
            after_sequence=0
        )
    )

    imported_events = [

        event

        for event

        in target_changes.events

        if (

            event.operation.value

            == "imported"

            and event.entity_type

            == "workspace_snapshot"
        )
    ]

    assert len(imported_events) == 1

    # Step 19 -- export again and
    # compare normalized payloads.

    restored_snapshot = (

        target_workspace
        .export_workspace()
    )

    assert (

        normalize_snapshot(
            restored_snapshot
        )

        == normalize_snapshot(
            snapshot
        )
    )


def test_workspace_gateway_read_only_operations_only_used_end_to_end():

    application = (
        PreReqAIApplication()
    )

    workspace = (

        application
        .research_workspace
    )

    workspace.create_session(
        "session-a"
    )

    checkpoint = (

        workspace
        .create_checkpoint(
            "session-a"
        )
    )

    assert checkpoint is not None

    before = (

        workspace
        .get_latest_change_sequence()
    )

    workspace.audit_workspace()

    workspace.plan_repairs()

    workspace.export_workspace()

    workspace.search_sessions(
        search="session"
    )

    workspace.get_workspace_insights()

    page = (

        workspace.get_changes(
            after_sequence=before
        )
    )

    assert page.events == []
