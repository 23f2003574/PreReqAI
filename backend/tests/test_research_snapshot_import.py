from copy import deepcopy

import pytest

from backend.session import (
    ResearchSnapshotImportStrategy,
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

    cp1 = (

        application
        .checkpoint_workflow_progress(
            "s1"
        )
    )

    application.branch_research_checkpoint(

        cp1.id,

        branch_session_id=(
            "math"
        ),

        display_name=(
            "Mathematical Route"
        ),
    )

    application.activate_research_session(
        "math"
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
            "spectral"
        ),

        display_name=(
            "Spectral Route"
        ),
    )

    application.branch_research_checkpoint(

        cp1.id,

        branch_session_id=(
            "implementation"
        ),

        display_name=(
            "Implementation Route"
        ),
    )

    application.tag_research_session(

        "root",

        "transformers",
    )

    application.tag_research_session(

        "math",

        "transformers",
    )

    application.tag_research_session(

        "math",

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

        "root",
    )

    application.add_research_session_to_collection(

        collection.id,

        "math",
    )

    application.compare_research_sessions(

        "root",

        "math",
    )

    return application


def normalized_domain_payload(

    snapshot,

):

    payload = snapshot.to_dict()

    payload.pop(
        "manifest"
    )

    return payload


def test_workspace_export_import_round_trip():

    source = (
        create_complex_workspace()
    )

    original = (

        source
        .export_research_workspace()
    )

    target = (
        PreReqAIApplication()
    )

    target.import_research_snapshot(

        original,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),
    )

    restored = (

        target
        .export_research_workspace()
    )

    assert (

        normalized_domain_payload(

            restored
        )

        ==

        normalized_domain_payload(

            original
        )
    )


def test_import_preview_does_not_mutate_workspace():

    application = (
        create_complex_workspace()
    )

    other = (
        create_complex_workspace()
    )

    snapshot = (

        other
        .export_research_session(
            "spectral"
        )
    )

    before = (

        application
        .export_research_workspace()
        .to_dict()
    )

    application.preview_research_snapshot_import(

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REMAP_ALL
        ),
    )

    after = (

        application
        .export_research_workspace()
        .to_dict()
    )

    before.pop("manifest")

    after.pop("manifest")

    assert before == after


def test_reject_strategy_refuses_session_id_conflict():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    other = (
        PreReqAIApplication()
    )

    other.activate_research_session(
        "session-a"
    )

    other.save_research_session(
        "session-a"
    )

    snapshot = (

        other
        .export_research_session(
            "session-a"
        )
    )

    plan = (

        application
        .preview_research_snapshot_import(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REJECT
            ),
        )
    )

    assert plan.has_conflicts

    with pytest.raises(
        ValueError
    ):

        application.import_research_snapshot(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REJECT
            ),
        )

    assert (

        len(
            application
            .session_manager
            .list_sessions()
        )

        == 1
    )


def test_remap_conflicts_changes_only_colliding_ids():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(
        "session-a"
    )

    application.save_research_session(
        "session-a"
    )

    other = (
        PreReqAIApplication()
    )

    other.activate_research_session(
        "session-a"
    )

    other.save_research_session(
        "session-a"
    )

    other.activate_research_session(
        "session-b"
    )

    other.save_research_session(
        "session-b"
    )

    snapshot = (

        other
        .export_research_workspace()
    )

    plan = (

        application
        .preview_research_snapshot_import(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REMAP_CONFLICTS
            ),
        )
    )

    assert (

        plan.identity_map
        .sessions["session-a"]

        != "session-a"
    )

    assert (

        plan.identity_map
        .sessions["session-b"]

        == "session-b"
    )


def test_remap_all_changes_every_imported_identity():

    application = (
        PreReqAIApplication()
    )

    source = (
        create_complex_workspace()
    )

    snapshot = (

        source
        .export_research_workspace()
    )

    plan = (

        application
        .preview_research_snapshot_import(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REMAP_ALL
            ),
        )
    )

    for (

        original_id,
        local_id,

    ) in (

        plan.identity_map
        .sessions.items()
    ):

        assert local_id != original_id

    for (

        original_id,
        local_id,

    ) in (

        plan.identity_map
        .checkpoints.items()
    ):

        assert local_id != original_id

    for (

        original_id,
        local_id,

    ) in (

        plan.identity_map
        .versions.items()
    ):

        assert local_id != original_id

    for (

        original_id,
        local_id,

    ) in (

        plan.identity_map
        .tags.items()
    ):

        assert local_id != original_id

    for (

        original_id,
        local_id,

    ) in (

        plan.identity_map
        .collections.items()
    ):

        assert local_id != original_id


def test_branch_references_follow_session_remapping():

    application = (
        PreReqAIApplication()
    )

    source = (
        PreReqAIApplication()
    )

    source.activate_research_session(
        "session-a"
    )

    checkpoint = (

        source
        .checkpoint_workflow_progress(
            "s1"
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
        .export_research_lineage(
            "session-a"
        )
    )

    plan = (

        application
        .preview_research_snapshot_import(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REMAP_ALL
            ),
        )
    )

    assert len(plan.branches) == 1

    branch = plan.branches[0]

    assert (

        branch[
            "source_session_id"
        ]

        ==

        plan.identity_map
        .sessions["session-a"]
    )

    assert (

        branch[
            "branch_session_id"
        ]

        ==

        plan.identity_map
        .sessions["session-b"]
    )


def test_every_reference_type_follows_remapping():

    application = (
        PreReqAIApplication()
    )

    source = (
        create_complex_workspace()
    )

    snapshot = (

        source
        .export_research_workspace()
    )

    plan = (

        application
        .preview_research_snapshot_import(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REMAP_ALL
            ),
        )
    )

    mapped_session_ids = set(

        plan.identity_map
        .sessions.values()
    )

    mapped_checkpoint_ids = set(

        plan.identity_map
        .checkpoints.values()
    )

    mapped_version_ids = set(

        plan.identity_map
        .versions.values()
    )

    mapped_tag_ids = set(

        plan.identity_map
        .tags.values()
    )

    mapped_collection_ids = set(

        plan.identity_map
        .collections.values()
    )

    for profile in plan.profiles:

        assert (

            profile["session_id"]

            in mapped_session_ids
        )

    for checkpoint in plan.checkpoints:

        assert (

            checkpoint["session_id"]

            in mapped_session_ids
        )

        if (

            checkpoint.get(
                "snapshot_version_id"
            )

            is not None
        ):

            assert (

                checkpoint[
                    "snapshot_version_id"
                ]

                in mapped_version_ids
            )

    for version in plan.versions:

        assert (

            version["session_id"]

            in mapped_session_ids
        )

    for branch in plan.branches:

        assert (

            branch[
                "source_session_id"
            ]

            in mapped_session_ids
        )

        assert (

            branch[
                "branch_session_id"
            ]

            in mapped_session_ids
        )

        assert (

            branch[
                "source_checkpoint_id"
            ]

            in mapped_checkpoint_ids
        )

        assert (

            branch[
                "source_version_id"
            ]

            in mapped_version_ids
        )

    for assignment in (

        plan.tag_assignments

    ):

        assert (

            assignment["session_id"]

            in mapped_session_ids
        )

        assert (

            assignment["tag_id"]

            in mapped_tag_ids
        )

    for membership in (

        plan.collection_memberships

    ):

        assert (

            membership["session_id"]

            in mapped_session_ids
        )

        assert (

            membership["collection_id"]

            in mapped_collection_ids
        )

    for event in plan.activity_events:

        if (

            event.get("session_id")

            is not None
        ):

            assert (

                event["session_id"]

                in mapped_session_ids
            )

        if (

            event.get(
                "related_session_id"
            )

            is not None
        ):

            assert (

                event[
                    "related_session_id"
                ]

                in mapped_session_ids
            )


def test_import_planning_does_not_mutate_original_snapshot():

    application = (
        PreReqAIApplication()
    )

    source = (
        create_complex_workspace()
    )

    snapshot = (

        source
        .export_research_workspace()
    )

    before = deepcopy(

        snapshot.to_dict()
    )

    application.preview_research_snapshot_import(

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REMAP_ALL
        ),
    )

    assert snapshot.to_dict() == before


def test_failed_import_rolls_back_all_mutations():

    application = (
        PreReqAIApplication()
    )

    source = (
        create_complex_workspace()
    )

    snapshot = (

        source
        .export_research_workspace()
    )

    def failing_save(*args, **kwargs):

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

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REJECT
            ),
        )

    assert (

        application
        .session_manager
        .list_sessions()

        == []
    )

    assert (

        application
        .session_profile_store
        .list_all()

        == []
    )

    assert (

        application
        .tag_store
        .list_tags()

        == []
    )

    assert (

        application
        .collection_store
        .list_collections()

        == []
    )

    assert (

        application
        .research_activity_store
        .list_all()

        == []
    )


def test_import_preserves_historical_activity_timestamps():

    source = (
        create_complex_workspace()
    )

    snapshot = (

        source
        .export_research_workspace()
    )

    original_timestamps = {

        event["id"]: event[
            "occurred_at"
        ]

        for event

        in snapshot.activity_events
    }

    application = (
        PreReqAIApplication()
    )

    application.import_research_snapshot(

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),
    )

    for event in (

        application
        .research_activity_store
        .list_all()
    ):

        assert (

            event.occurred_at
            .isoformat()

            == original_timestamps[
                event.id
            ]
        )


def test_import_restores_activity_without_emitting_new_domain_events():

    source = (
        create_complex_workspace()
    )

    snapshot = (

        source
        .export_research_workspace()
    )

    expected_count = len(

        snapshot.activity_events
    )

    application = (
        PreReqAIApplication()
    )

    application.import_research_snapshot(

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),
    )

    assert (

        len(

            application
            .research_activity_store
            .list_all()
        )

        == expected_count
    )


def test_same_snapshot_can_be_imported_twice_with_remap_all():

    application = (
        PreReqAIApplication()
    )

    source = (
        create_complex_workspace()
    )

    snapshot = (

        source
        .export_research_session_tree(
            "root"
        )
    )

    first = (

        application.import_research_snapshot(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REMAP_ALL
            ),
        )
    )

    second = (

        application.import_research_snapshot(

            snapshot,

            strategy=(

                ResearchSnapshotImportStrategy
                .REMAP_ALL
            ),
        )
    )

    assert (

        set(

            first.identity_map
            .sessions.values()
        )
        .isdisjoint(

            set(

                second.identity_map
                .sessions.values()
            )
        )
    )


def test_invalid_snapshot_is_rejected_before_mutation():

    application = (
        PreReqAIApplication()
    )

    source = (
        create_complex_workspace()
    )

    snapshot = (

        source
        .export_research_session(
            "root"
        )
    )

    snapshot.tag_assignments.append({

        "session_id":
            "root",

        "tag_id":
            "missing-tag",
    })

    with pytest.raises(
        ValueError
    ):

        application.import_research_snapshot(

            snapshot
        )

    assert (

        application
        .session_manager
        .list_sessions()

        == []
    )
