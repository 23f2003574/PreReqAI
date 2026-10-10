from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    InMemoryResearchActivityStore,
    InMemoryResearchCheckpointStore,
    InMemoryResearchCollectionStore,
    InMemoryResearchSessionBranchStore,
    InMemoryResearchSessionProfileStore,
    InMemoryResearchSessionStore,
    InMemoryResearchSessionVersionStore,
    InMemoryResearchTagStore,
    ResearchSessionLineageService,
    ResearchSessionManager,
    ResearchSessionSnapshot,
    ResearchSnapshotScope,
    ResearchSnapshotService,
    ResearchSnapshotValidator,
)

from frontend.src.app import (
    PreReqAIApplication,
)


def create_workspace_with_branch():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "root"
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
            "child"
        ),
    )

    return application


def create_branching_workspace():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "root"
    )

    cp1 = (

        application
        .checkpoint_workflow_progress(
            "s1"
        )
    )

    application.branch_research_checkpoint(

        cp1.id,

        branch_session_id=(
            "child-a"
        ),
    )

    application.branch_research_checkpoint(

        cp1.id,

        branch_session_id=(
            "child-b"
        ),
    )

    application.activate_research_session(
        "child-a"
    )

    cp2 = (

        application
        .checkpoint_workflow_progress(
            "s2"
        )
    )

    application.branch_research_checkpoint(

        cp2.id,

        branch_session_id=(
            "grandchild"
        ),
    )

    return application


def create_multi_lineage_workspace():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "root-1"
    )

    cp1 = (

        application
        .checkpoint_workflow_progress(
            "s1"
        )
    )

    application.branch_research_checkpoint(

        cp1.id,

        branch_session_id=(
            "child-1a"
        ),
    )

    application.branch_research_checkpoint(

        cp1.id,

        branch_session_id=(
            "child-1b"
        ),
    )

    application.activate_research_session(
        "root-2"
    )

    cp2 = (

        application
        .checkpoint_workflow_progress(
            "s2"
        )
    )

    application.branch_research_checkpoint(

        cp2.id,

        branch_session_id=(
            "child-2a"
        ),
    )

    application.activate_research_session(
        "child-2a"
    )

    cp3 = (

        application
        .checkpoint_workflow_progress(
            "s3"
        )
    )

    application.branch_research_checkpoint(

        cp3.id,

        branch_session_id=(
            "grandchild-2a"
        ),
    )

    application.activate_research_session(
        "root-3"
    )

    application.save_research_session(
        "root-3"
    )

    return application


def create_tagged_workspace():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.activate_research_session(
        "session-b"
    )

    application.save_research_session(
        "session-b"
    )

    application.tag_research_session(

        "session-a",

        "transformers",
    )

    application.tag_research_session(

        "session-a",

        "math-heavy",
    )

    application.tag_research_session(

        "session-b",

        "implementation",
    )

    return application


def create_collection_workspace():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.activate_research_session(
        "session-b"
    )

    application.save_research_session(
        "session-b"
    )

    collection = (

        application
        .create_research_collection(

            "Current Research"
        )
    )

    application.add_research_session_to_collection(

        collection.id,

        "session-a",
    )

    application.add_research_session_to_collection(

        collection.id,

        "session-b",
    )

    return application


def create_workspace_with_cross_session_activity():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    application.activate_research_session(
        "session-b"
    )

    application.save_research_session(
        "session-b"
    )

    application.tag_research_session(

        "session-a",

        "solo-tag",
    )

    application.compare_research_sessions(

        "session-a",

        "session-b",
    )

    application.tag_research_session(

        "session-b",

        "other-tag",
    )

    return application


def create_workspace_with_activity():

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

    return application


def create_complex_workspace():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "root-a"
    )

    application.save_research_session(
        "root-a"
    )

    application.update_research_session_profile(

        "root-a",

        display_name="Root A",

        status="active",
    )

    cp = (

        application
        .checkpoint_workflow_progress(
            "s1"
        )
    )

    application.branch_research_checkpoint(

        cp.id,

        branch_session_id=(
            "branch-a1"
        ),

        display_name=(
            "Branch A1"
        ),
    )

    application.pause_research_session(
        "branch-a1"
    )

    application.tag_research_session(

        "branch-a1",

        "transformers",
    )

    application.tag_research_session(

        "root-a",

        "math-heavy",
    )

    collection = (

        application
        .create_research_collection(

            "Current Research"
        )
    )

    application.add_research_session_to_collection(

        collection.id,

        "root-a",
    )

    application.add_research_session_to_collection(

        collection.id,

        "branch-a1",
    )

    application.compare_research_sessions(

        "root-a",

        "branch-a1",
    )

    application.activate_research_session(
        "root-b"
    )

    application.save_research_session(
        "root-b"
    )

    application.complete_research_session(
        "root-b"
    )

    return application


def create_snapshot_service(

    clock=None,

    id_factory=None,

):

    session_store = (
        InMemoryResearchSessionStore()
    )

    session_store.save(

        ResearchSessionSnapshot(

            session_id="session-a"
        )
    )

    session_store.save(

        ResearchSessionSnapshot(

            session_id="session-b"
        )
    )

    branch_store = (
        InMemoryResearchSessionBranchStore()
    )

    return (

        ResearchSnapshotService(

            session_manager=(

                ResearchSessionManager(
                    session_store
                )
            ),

            profile_store=(
                InMemoryResearchSessionProfileStore()
            ),

            checkpoint_store=(
                InMemoryResearchCheckpointStore()
            ),

            version_store=(
                InMemoryResearchSessionVersionStore()
            ),

            branch_store=(
                branch_store
            ),

            lineage_service=(

                ResearchSessionLineageService(

                    branch_store=(
                        branch_store
                    )
                )
            ),

            tag_store=(
                InMemoryResearchTagStore()
            ),

            collection_store=(
                InMemoryResearchCollectionStore()
            ),

            activity_store=(
                InMemoryResearchActivityStore()
            ),

            validator=(
                ResearchSnapshotValidator()
            ),

            clock=clock,

            id_factory=id_factory,
        )
    )


def test_single_session_export_contains_only_selected_session():

    application = (
        create_workspace_with_branch()
    )

    snapshot = (

        application
        .export_research_session(
            "child"
        )
    )

    session_ids = {

        item["session_id"]

        for item

        in snapshot.sessions
    }

    assert session_ids == {
        "child"
    }

    assert snapshot.branches == []


def test_session_tree_export_contains_descendants_only():

    application = (
        create_branching_workspace()
    )

    snapshot = (

        application
        .export_research_session_tree(
            "child-a"
        )
    )

    session_ids = {

        item["session_id"]

        for item

        in snapshot.sessions
    }

    assert session_ids == {

        "child-a",

        "grandchild",
    }

    assert "root" not in session_ids

    assert "child-b" not in session_ids


def test_lineage_export_contains_complete_research_tree():

    application = (
        create_branching_workspace()
    )

    snapshot = (

        application
        .export_research_lineage(
            "child-a"
        )
    )

    session_ids = {

        item["session_id"]

        for item

        in snapshot.sessions
    }

    assert session_ids == {

        "root",

        "child-a",

        "grandchild",

        "child-b",
    }


def test_workspace_export_contains_all_sessions():

    application = (
        create_multi_lineage_workspace()
    )

    snapshot = (

        application
        .export_research_workspace()
    )

    assert (

        len(
            snapshot.sessions
        )

        == 7
    )

    assert (

        snapshot.manifest.scope

        == (
            ResearchSnapshotScope
            .WORKSPACE
        )
    )

    assert (

        snapshot.manifest
        .root_session_id

        is None
    )


def test_export_contains_only_tags_used_by_included_sessions():

    application = (
        create_tagged_workspace()
    )

    snapshot = (

        application
        .export_research_session(
            "session-a"
        )
    )

    tag_names = {

        tag["name"]

        for tag

        in snapshot.tags
    }

    assert tag_names == {

        "transformers",

        "math-heavy",
    }


def test_export_filters_collection_memberships_to_included_sessions():

    application = (
        create_collection_workspace()
    )

    snapshot = (

        application
        .export_research_session(
            "session-a"
        )
    )

    assert all(

        membership["session_id"]

        == "session-a"

        for membership

        in snapshot
        .collection_memberships
    )

    assert (

        len(
            snapshot
            .collection_memberships
        )

        == 1
    )


def test_export_excludes_activity_with_external_session_references():

    application = (
        create_workspace_with_cross_session_activity()
    )

    snapshot = (

        application
        .export_research_session(
            "session-a"
        )
    )

    for event in (

        snapshot.activity_events

    ):

        references = {

            event.get(
                "session_id"
            ),

            event.get(
                "related_session_id"
            ),
        }

        references.discard(
            None
        )

        assert references.issubset({

            "session-a"
        })

    assert any(

        event["activity_type"]

        == "tag.assigned"

        for event

        in snapshot.activity_events
    )


def test_export_does_not_create_activity_events():

    application = (
        create_workspace_with_activity()
    )

    before = len(

        application
        .research_activity_store
        .list_all()
    )

    application.export_research_workspace()

    after = len(

        application
        .research_activity_store
        .list_all()
    )

    assert after == before


def test_snapshot_records_are_deterministically_ordered():

    fixed_now = datetime(

        2026,
        7,
        13,
        12,
        0,

        tzinfo=timezone.utc,
    )

    service = (

        create_snapshot_service(

            clock=lambda: fixed_now,

            id_factory=(

                lambda:
                    "snapshot-fixed"
            ),
        )
    )

    first = (

        service.build_snapshot(

            ResearchSnapshotScope
            .WORKSPACE
        )
    )

    second = (

        service.build_snapshot(

            ResearchSnapshotScope
            .WORKSPACE
        )
    )

    assert (

        first.to_dict()

        == second.to_dict()
    )


def test_generated_workspace_snapshot_is_valid():

    application = (
        create_complex_workspace()
    )

    snapshot = (

        application
        .export_research_workspace()
    )

    result = (

        application
        .research_snapshot_validator
        .validate(
            snapshot
        )
    )

    assert result.is_valid is True
