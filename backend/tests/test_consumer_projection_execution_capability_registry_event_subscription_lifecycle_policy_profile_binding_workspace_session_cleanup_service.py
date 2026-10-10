import time

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupPolicy as Policy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupService as CleanupService,
)


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    tracked_ids = []

    def _sessions_provider():
        return [session_service.session(session_id) for session_id in tracked_ids]

    return pipeline_service, session_service, tracked_ids, _sessions_provider


def _create_pipeline(pipeline_service, pipeline_id):
    pipeline_service.create(
        Pipeline(
            pipeline_id=pipeline_id,
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )


def _start_session(pipeline_service, session_service, tracked_ids, pipeline_id, owner="user-1"):
    _create_pipeline(pipeline_service, pipeline_id)
    session = session_service.start(pipeline_id, owner=owner)
    tracked_ids.append(session.session_id)
    return session


class TestWorkspaceSessionCleanupService:
    def test_preview_cleanup(self):
        pipeline_service, session_service, tracked_ids, sessions_provider = _build()
        session = _start_session(pipeline_service, session_service, tracked_ids, "pipeline-1")
        session_service.finish(session.session_id, successful=True)

        policy = Policy(policy_id="policy-1", max_age=0.01, completed_only=True, archive_before_delete=False)
        cleanup_service = CleanupService(sessions_provider, policies=[policy])

        time.sleep(0.05)

        result = cleanup_service.preview()

        assert isinstance(result, Result)
        assert result.scanned == 1
        assert result.deleted == 1

        # preview() must not mutate: statistics stay at zero and the session is still expired
        assert cleanup_service.statistics() == Result(scanned=0, archived=0, deleted=0)
        assert [s.session_id for s in cleanup_service.expired()] == [session.session_id]

    def test_cleanup_execution(self):
        pipeline_service, session_service, tracked_ids, sessions_provider = _build()
        session = _start_session(pipeline_service, session_service, tracked_ids, "pipeline-1")
        session_service.finish(session.session_id, successful=True)

        policy = Policy(policy_id="policy-1", max_age=0.01, completed_only=True, archive_before_delete=False)
        cleanup_service = CleanupService(sessions_provider, policies=[policy])

        time.sleep(0.05)

        result = cleanup_service.run()

        assert result.scanned == 1
        assert result.deleted == 1
        assert cleanup_service.expired() == ()

        # a second run no longer counts the already-retired session
        second = cleanup_service.run()
        assert second.scanned == 1
        assert second.deleted == 0

    def test_archive_before_delete(self):
        pipeline_service, session_service, tracked_ids, sessions_provider = _build()
        session = _start_session(pipeline_service, session_service, tracked_ids, "pipeline-1")
        session_service.finish(session.session_id, successful=True)

        archiving_policy = Policy(policy_id="policy-1", max_age=0.01, completed_only=True, archive_before_delete=True)
        cleanup_service = CleanupService(sessions_provider, policies=[archiving_policy])

        time.sleep(0.05)

        result = cleanup_service.run()

        assert result.archived == 1
        assert result.deleted == 1

    def test_active_session_protection(self):
        pipeline_service, session_service, tracked_ids, sessions_provider = _build()
        active_session = _start_session(pipeline_service, session_service, tracked_ids, "pipeline-1")
        finished_session = _start_session(pipeline_service, session_service, tracked_ids, "pipeline-2")
        session_service.finish(finished_session.session_id, successful=True)

        policy = Policy(policy_id="policy-1", max_age=0.01, completed_only=False, archive_before_delete=False)
        cleanup_service = CleanupService(sessions_provider, policies=[policy])

        time.sleep(0.05)

        result = cleanup_service.run()

        assert result.scanned == 2
        assert result.deleted == 1

        expired_ids = {s.session_id for s in cleanup_service.expired()}
        assert active_session.session_id not in expired_ids

    def test_statistics_generation(self):
        pipeline_service, session_service, tracked_ids, sessions_provider = _build()
        session_one = _start_session(pipeline_service, session_service, tracked_ids, "pipeline-1")
        session_service.finish(session_one.session_id, successful=True)

        policy = Policy(policy_id="policy-1", max_age=0.01, completed_only=True, archive_before_delete=True)
        cleanup_service = CleanupService(sessions_provider, policies=[policy])

        time.sleep(0.05)

        cleanup_service.run()

        session_two = _start_session(pipeline_service, session_service, tracked_ids, "pipeline-2")
        session_service.finish(session_two.session_id, successful=True)

        time.sleep(0.05)

        cleanup_service.run()

        stats = cleanup_service.statistics()
        assert isinstance(stats, Result)
        assert stats.scanned == 3  # 1 session scanned on the first run, 2 (both tracked) on the second
        assert stats.archived == 2
        assert stats.deleted == 2

    def test_invalid_policy_rejection(self):
        _pipeline_service, _session_service, _tracked_ids, sessions_provider = _build()
        cleanup_service = CleanupService(sessions_provider)

        with pytest.raises(Error):
            cleanup_service.apply("   ")

        with pytest.raises(Error):
            cleanup_service.apply("unknown-policy")

        with pytest.raises(Error):
            Policy(policy_id="policy-1", max_age=0, completed_only=True, archive_before_delete=False)

        with pytest.raises(Error):
            Policy(policy_id="policy-1", max_age=-5, completed_only=True, archive_before_delete=False)
