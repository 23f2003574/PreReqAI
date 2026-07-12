from datetime import datetime

import pytest

from backend.session import (

    ResearchCheckpoint,

    ResearchCheckpointReason,
)

from frontend.src import (
    PreReqAIApplication,
)


def test_recovers_historical_checkpoint_without_deleting_newer_history():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-1",

        paper_title="State A",
    )

    checkpoint_a = (

        application
        .checkpoint_workflow_progress(

            "step-a"
        )
    )

    application.active_paper_title = (
        "State B"
    )

    checkpoint_b = (

        application
        .checkpoint_workflow_progress(

            "step-b"
        )
    )

    result = (

        application
        .restore_research_checkpoint(

            checkpoint_a.id
        )
    )

    checkpoints = (

        application
        .research_checkpoints(

            "session-1"
        )
    )

    assert (

        application
        .active_paper_title

        == "State A"
    )

    assert (

        application
        .get_research_checkpoint(

            checkpoint_b.id
        )

        is not None
    )

    assert (

        result.source_checkpoint_id

        == checkpoint_a.id
    )

    assert (

        result.safety_checkpoint_id

        is not None
    )

    assert (

        result.recovery_checkpoint_id

        is not None
    )

    assert len(checkpoints) == 4


def test_recovery_safety_checkpoint_preserves_previous_current_state():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        session_id="session-1",

        paper_title="Old State",
    )

    old_checkpoint = (

        application
        .checkpoint_workflow_progress(

            "old-step"
        )
    )

    application.active_paper_title = (
        "Current State"
    )

    result = (

        application
        .restore_research_checkpoint(

            old_checkpoint.id
        )
    )

    safety_version = (

        application
        .research_checkpoint_version(

            result
            .safety_checkpoint_id
        )
    )

    assert safety_version is not None

    assert (

        safety_version
        .snapshot
        .paper_title

        == "Current State"
    )


def test_cannot_restore_checkpoint_from_another_session():

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

        application.restore_research_checkpoint(

            checkpoint.id
        )


def test_recovery_rejects_unknown_checkpoint():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-1"
    )

    with pytest.raises(

        ValueError,

        match=(
            "does not exist"
        ),
    ):

        application.restore_research_checkpoint(

            "missing-checkpoint"
        )


def test_recovery_rejects_checkpoint_without_version():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-1"
    )

    legacy_checkpoint = (

        ResearchCheckpoint(

            session_id="session-1",

            reason=(

                ResearchCheckpointReason
                .MANUAL
            ),

            snapshot_updated_at=(
                datetime.utcnow()
            ),

            snapshot_version_id=None,
        )
    )

    application.checkpoint_store.save(

        legacy_checkpoint
    )

    with pytest.raises(

        ValueError,

        match=(

            "does not reference an "
            "immutable session version"
        ),
    ):

        application.restore_research_checkpoint(

            legacy_checkpoint.id
        )


def test_recovery_checkpoint_records_source_metadata():

    application = (
        PreReqAIApplication()
    )

    application.activate_research_session(

        "session-1"
    )

    source = (

        application
        .checkpoint_workflow_progress(

            "step-1"
        )
    )

    result = (

        application
        .restore_research_checkpoint(

            source.id
        )
    )

    recovery_checkpoint = (

        application
        .get_research_checkpoint(

            result
            .recovery_checkpoint_id
        )
    )

    assert (

        recovery_checkpoint
        .metadata[
            "source_checkpoint_id"
        ]

        == source.id
    )

    assert (

        recovery_checkpoint
        .metadata[
            "source_version_id"
        ]

        == (
            source
            .snapshot_version_id
        )
    )

    assert (

        recovery_checkpoint
        .metadata[
            "safety_checkpoint_id"
        ]

        == (
            result
            .safety_checkpoint_id
        )
    )
