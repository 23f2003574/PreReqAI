import time

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeat as Heartbeat,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatService as HeartbeatService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHeartbeatStatus as HeartbeatStatus,
)


def _build(stale_timeout_seconds=60.0):
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    heartbeat_service = HeartbeatService(session_service, stale_timeout_seconds=stale_timeout_seconds)
    return pipeline_service, session_service, heartbeat_service


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


class TestWorkspaceSessionHeartbeatService:
    def test_record_heartbeat(self):
        pipeline_service, session_service, heartbeat_service = _build()
        session = _start_session(pipeline_service, session_service)

        heartbeat = heartbeat_service.beat(session.session_id, 1)

        assert isinstance(heartbeat, Heartbeat)
        assert heartbeat.session_id == session.session_id
        assert heartbeat.sequence == 1

    def test_session_status(self):
        pipeline_service, session_service, heartbeat_service = _build()
        session = _start_session(pipeline_service, session_service)

        never_beaten = heartbeat_service.status(session.session_id)
        assert isinstance(never_beaten, HeartbeatStatus)
        assert never_beaten.healthy is False
        assert never_beaten.last_seen is None

        heartbeat_service.beat(session.session_id, 1)

        healthy = heartbeat_service.status(session.session_id)
        assert healthy.healthy is True
        assert healthy.last_seen is not None

    def test_stale_session_detection(self):
        pipeline_service, session_service, heartbeat_service = _build(stale_timeout_seconds=0.05)
        session = _start_session(pipeline_service, session_service)

        heartbeat_service.beat(session.session_id, 1)
        assert heartbeat_service.stale() == ()

        time.sleep(0.1)

        stale = heartbeat_service.stale()
        assert [status.session_id for status in stale] == [session.session_id]
        assert stale[0].healthy is False

    def test_expire_session(self):
        pipeline_service, session_service, heartbeat_service = _build()
        session = _start_session(pipeline_service, session_service)

        heartbeat_service.beat(session.session_id, 1)
        assert heartbeat_service.status(session.session_id).healthy is True

        heartbeat_service.mark_expired(session.session_id)
        assert heartbeat_service.status(session.session_id).healthy is False

        # a fresh heartbeat clears the manual expiry
        heartbeat_service.beat(session.session_id, 2)
        assert heartbeat_service.status(session.session_id).healthy is True

    def test_duplicate_sequence_rejection(self):
        pipeline_service, session_service, heartbeat_service = _build()
        session = _start_session(pipeline_service, session_service)

        heartbeat_service.beat(session.session_id, 5)

        with pytest.raises(Error):
            heartbeat_service.beat(session.session_id, 5)

        with pytest.raises(Error):
            heartbeat_service.beat(session.session_id, 3)

    def test_cleanup_old_heartbeats(self):
        pipeline_service, session_service, heartbeat_service = _build()
        session = _start_session(pipeline_service, session_service)

        heartbeat_service.beat(session.session_id, 1)
        assert heartbeat_service.cleanup() == ()

        session_service.finish(session.session_id, successful=True)

        removed = heartbeat_service.cleanup()
        assert removed == (session.session_id,)

        # heartbeat state was purged; a fresh lookup starts from scratch
        with pytest.raises(Error):
            heartbeat_service.beat(session.session_id, 2)

    def test_heartbeat_for_completed_session_rejection(self):
        pipeline_service, session_service, heartbeat_service = _build()
        session = _start_session(pipeline_service, session_service)

        session_service.finish(session.session_id, successful=True)

        with pytest.raises(Error):
            heartbeat_service.beat(session.session_id, 1)

    def test_blank_and_unknown_id_rejection(self):
        _pipeline_service, _session_service, heartbeat_service = _build()

        with pytest.raises(Error):
            heartbeat_service.beat("   ", 1)

        with pytest.raises(Error):
            heartbeat_service.beat("unknown-session", 1)

        with pytest.raises(Error):
            heartbeat_service.status("   ")

        with pytest.raises(Error):
            heartbeat_service.status("unknown-session")

        with pytest.raises(Error):
            heartbeat_service.mark_expired("   ")

        with pytest.raises(Error):
            heartbeat_service.mark_expired("unknown-session")
