import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSession as Session,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus as Status,
)


def _build(stage_executors=None):
    pipeline_service = PipelineService(
        stage_executors=stage_executors if stage_executors is not None else {"validation": lambda w, c: None}
    )
    session_service = SessionService(pipeline_service)
    return pipeline_service, session_service


def _create_pipeline(pipeline_service, pipeline_id):
    pipeline_service.create(
        Pipeline(
            pipeline_id=pipeline_id,
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )


class TestWorkspaceExecutionSessionService:
    def test_start_session(self):
        pipeline_service, session_service = _build()
        _create_pipeline(pipeline_service, "pipeline-1")

        session = session_service.start("pipeline-1", owner="user-1")

        assert isinstance(session, Session)
        assert session.pipeline_id == "pipeline-1"
        assert session.owner == "user-1"
        assert session.status == Status.ACTIVE
        assert session.finished_at is None
        assert session_service.session(session.session_id) == session

    def test_finish_session(self):
        pipeline_service, session_service = _build()
        _create_pipeline(pipeline_service, "pipeline-1")

        session = session_service.start("pipeline-1", owner="user-1")
        result = session_service.finish(session.session_id, successful=True)

        assert isinstance(result, Result)
        assert result.session_id == session.session_id
        assert result.successful is True

        finished = session_service.session(session.session_id)
        assert finished.status == Status.FINISHED
        assert finished.finished_at is not None

        # finishing releases runtime resources: a new session can now start
        restarted = session_service.start("pipeline-1", owner="user-2")
        assert restarted.session_id != session.session_id

    def test_cancel_session(self):
        pipeline_service, session_service = _build()
        _create_pipeline(pipeline_service, "pipeline-1")

        session = session_service.start("pipeline-1", owner="user-1")
        cancelled = session_service.cancel(session.session_id)

        assert cancelled.status == Status.CANCELLED
        assert cancelled.finished_at is not None

        # cancelled sessions remain queryable
        assert session_service.session(session.session_id).status == Status.CANCELLED

        # cancelling releases runtime resources: a new session can now start
        restarted = session_service.start("pipeline-1", owner="user-2")
        assert restarted.session_id != session.session_id

    def test_active_session_lookup(self):
        pipeline_service, session_service = _build()
        _create_pipeline(pipeline_service, "pipeline-1")
        _create_pipeline(pipeline_service, "pipeline-2")

        assert session_service.active() == ()

        session_one = session_service.start("pipeline-1", owner="user-1")
        session_two = session_service.start("pipeline-2", owner="user-2")

        active = session_service.active()
        assert set(session.session_id for session in active) == {session_one.session_id, session_two.session_id}

        session_service.finish(session_one.session_id, successful=True)

        active = session_service.active()
        assert [session.session_id for session in active] == [session_two.session_id]

    def test_duplicate_session_rejection(self):
        pipeline_service, session_service = _build()
        _create_pipeline(pipeline_service, "pipeline-1")

        session_service.start("pipeline-1", owner="user-1")

        with pytest.raises(Error):
            session_service.start("pipeline-1", owner="user-2")

    def test_completed_session_rejection(self):
        pipeline_service, session_service = _build()
        _create_pipeline(pipeline_service, "pipeline-1")

        session = session_service.start("pipeline-1", owner="user-1")
        session_service.finish(session.session_id, successful=True)

        with pytest.raises(Error):
            session_service.finish(session.session_id, successful=True)

        with pytest.raises(Error):
            session_service.cancel(session.session_id)

    def test_blank_id_rejection(self):
        _pipeline_service, session_service = _build()

        with pytest.raises(Error):
            session_service.start("   ", owner="user-1")

        with pytest.raises(Error):
            session_service.start("pipeline-1", owner="   ")

        with pytest.raises(Error):
            session_service.finish("   ", successful=True)

        with pytest.raises(Error):
            session_service.cancel("   ")

        with pytest.raises(Error):
            session_service.session("   ")

    def test_unknown_pipeline_and_session_rejection(self):
        _pipeline_service, session_service = _build()

        with pytest.raises(Error):
            session_service.start("unknown-pipeline", owner="user-1")

        with pytest.raises(Error):
            session_service.session("unknown-session")

        with pytest.raises(Error):
            session_service.finish("unknown-session", successful=True)

        with pytest.raises(Error):
            session_service.cancel("unknown-session")
