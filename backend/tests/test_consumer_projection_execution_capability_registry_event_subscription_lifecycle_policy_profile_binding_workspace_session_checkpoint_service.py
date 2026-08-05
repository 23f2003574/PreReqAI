import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpoint as Checkpoint,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCheckpointService as CheckpointService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRestoreResult as RestoreResult,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    checkpoint_service = CheckpointService(session_service)
    return pipeline_service, session_service, checkpoint_service


def _create_pipeline(pipeline_service, pipeline_id):
    pipeline_service.create(
        Pipeline(
            pipeline_id=pipeline_id,
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )


def _start_session(pipeline_service, session_service, pipeline_id="pipeline-1", owner="user-1"):
    _create_pipeline(pipeline_service, pipeline_id)
    return session_service.start(pipeline_id, owner=owner)


class TestWorkspaceSessionCheckpointService:
    def test_create_checkpoint(self):
        pipeline_service, session_service, checkpoint_service = _build()
        session = _start_session(pipeline_service, session_service)

        checkpoint = checkpoint_service.create(session.session_id, "stage-1", {"progress": 1})

        assert isinstance(checkpoint, Checkpoint)
        assert checkpoint.session_id == session.session_id
        assert checkpoint.stage_id == "stage-1"
        assert checkpoint.state == {"progress": 1}

    def test_restore_checkpoint(self):
        pipeline_service, session_service, checkpoint_service = _build()
        session = _start_session(pipeline_service, session_service)

        checkpoint = checkpoint_service.create(session.session_id, "stage-1", {"progress": 1})
        result = checkpoint_service.restore(checkpoint.checkpoint_id)

        assert isinstance(result, RestoreResult)
        assert result.session_id == session.session_id
        assert result.checkpoint_id == checkpoint.checkpoint_id
        assert result.restored is True

    def test_latest_checkpoint_lookup(self):
        pipeline_service, session_service, checkpoint_service = _build()
        session = _start_session(pipeline_service, session_service)

        assert checkpoint_service.latest(session.session_id) is None

        checkpoint_service.create(session.session_id, "stage-1", {"progress": 1})
        second = checkpoint_service.create(session.session_id, "stage-2", {"progress": 2})

        assert checkpoint_service.latest(session.session_id).checkpoint_id == second.checkpoint_id

    def test_checkpoint_history(self):
        pipeline_service, session_service, checkpoint_service = _build()
        session = _start_session(pipeline_service, session_service)

        first = checkpoint_service.create(session.session_id, "stage-1", {"progress": 1})
        second = checkpoint_service.create(session.session_id, "stage-2", {"progress": 2})

        history = checkpoint_service.history(session.session_id)

        assert [checkpoint.checkpoint_id for checkpoint in history] == [first.checkpoint_id, second.checkpoint_id]

    def test_remove_checkpoint(self):
        pipeline_service, session_service, checkpoint_service = _build()
        session = _start_session(pipeline_service, session_service)

        first = checkpoint_service.create(session.session_id, "stage-1", {"progress": 1})
        second = checkpoint_service.create(session.session_id, "stage-2", {"progress": 2})

        checkpoint_service.remove(first.checkpoint_id)

        assert [checkpoint.checkpoint_id for checkpoint in checkpoint_service.history(session.session_id)] == [
            second.checkpoint_id
        ]

        with pytest.raises(Error):
            checkpoint_service.restore(first.checkpoint_id)

    def test_invalid_restore_rejection(self):
        pipeline_service, session_service, checkpoint_service = _build()
        session = _start_session(pipeline_service, session_service)

        checkpoint = checkpoint_service.create(session.session_id, "stage-1", {"progress": 1})

        session_service.finish(session.session_id, successful=True)

        with pytest.raises(Error):
            checkpoint_service.restore(checkpoint.checkpoint_id)

        with pytest.raises(Error):
            checkpoint_service.restore("unknown-checkpoint")

        with pytest.raises(Error):
            checkpoint_service.restore("   ")

    def test_blank_and_unknown_id_rejection(self):
        pipeline_service, session_service, checkpoint_service = _build()
        session = _start_session(pipeline_service, session_service)

        with pytest.raises(Error):
            checkpoint_service.create("   ", "stage-1", {})

        with pytest.raises(Error):
            checkpoint_service.create(session.session_id, "   ", {})

        with pytest.raises(Error):
            checkpoint_service.create("unknown-session", "stage-1", {})

        with pytest.raises(Error):
            checkpoint_service.latest("unknown-session")

        with pytest.raises(Error):
            checkpoint_service.history("unknown-session")

        with pytest.raises(Error):
            checkpoint_service.remove("unknown-checkpoint")

        with pytest.raises(Error):
            checkpoint_service.remove("   ")
