import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwner as Owner,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionOwnershipService as OwnershipService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionTransferResult as TransferResult,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    ownership_service = OwnershipService(session_service)
    return pipeline_service, session_service, ownership_service


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


class TestWorkspaceSessionOwnershipService:
    def test_assign_owner(self):
        pipeline_service, session_service, ownership_service = _build()
        session = _start_session(pipeline_service, session_service)

        record = ownership_service.assign(session.session_id, "worker-1")

        assert isinstance(record, Owner)
        assert record.session_id == session.session_id
        assert record.owner_id == "worker-1"

        with pytest.raises(Error):
            ownership_service.assign(session.session_id, "worker-2")

    def test_transfer_ownership(self):
        pipeline_service, session_service, ownership_service = _build()
        session = _start_session(pipeline_service, session_service)

        ownership_service.assign(session.session_id, "worker-1")
        result = ownership_service.transfer(session.session_id, "worker-2")

        assert isinstance(result, TransferResult)
        assert result.session_id == session.session_id
        assert result.previous_owner == "worker-1"
        assert result.current_owner == "worker-2"
        assert result.transferred is True

        assert ownership_service.owner(session.session_id).owner_id == "worker-2"

    def test_release_ownership(self):
        pipeline_service, session_service, ownership_service = _build()
        session = _start_session(pipeline_service, session_service)

        ownership_service.assign(session.session_id, "worker-1")
        ownership_service.release(session.session_id)

        assert ownership_service.owner(session.session_id) is None

        # released sessions become unowned and can be assign()-ed again
        record = ownership_service.assign(session.session_id, "worker-2")
        assert record.owner_id == "worker-2"

        # releasing an already-unowned session is not an error
        ownership_service.release(session.session_id)

    def test_owner_lookup(self):
        pipeline_service, session_service, ownership_service = _build()
        session = _start_session(pipeline_service, session_service)

        assert ownership_service.owner(session.session_id) is None

        ownership_service.assign(session.session_id, "worker-1")

        assert ownership_service.owner(session.session_id).owner_id == "worker-1"

    def test_ownership_history(self):
        pipeline_service, session_service, ownership_service = _build()
        session = _start_session(pipeline_service, session_service)

        ownership_service.assign(session.session_id, "worker-1")
        ownership_service.transfer(session.session_id, "worker-2")
        ownership_service.transfer(session.session_id, "worker-3")
        ownership_service.release(session.session_id)

        history = ownership_service.history(session.session_id)

        assert [record.owner_id for record in history] == ["worker-1", "worker-2", "worker-3"]

    def test_invalid_transfer_rejection(self):
        pipeline_service, session_service, ownership_service = _build()
        session = _start_session(pipeline_service, session_service)

        # no active owner yet
        with pytest.raises(Error):
            ownership_service.transfer(session.session_id, "worker-1")

        ownership_service.assign(session.session_id, "worker-1")

        # transferring to the current owner
        with pytest.raises(Error):
            ownership_service.transfer(session.session_id, "worker-1")

        # transferring a completed session
        session_service.finish(session.session_id, successful=True)

        with pytest.raises(Error):
            ownership_service.transfer(session.session_id, "worker-2")

    def test_blank_and_unknown_id_rejection(self):
        pipeline_service, session_service, ownership_service = _build()
        session = _start_session(pipeline_service, session_service)

        with pytest.raises(Error):
            ownership_service.assign("   ", "worker-1")

        with pytest.raises(Error):
            ownership_service.assign(session.session_id, "   ")

        with pytest.raises(Error):
            ownership_service.assign("unknown-session", "worker-1")

        with pytest.raises(Error):
            ownership_service.transfer("   ", "worker-1")

        with pytest.raises(Error):
            ownership_service.owner("unknown-session")

        with pytest.raises(Error):
            ownership_service.history("unknown-session")

        with pytest.raises(Error):
            ownership_service.release("unknown-session")
