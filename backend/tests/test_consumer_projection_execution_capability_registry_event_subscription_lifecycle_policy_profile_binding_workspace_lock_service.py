import time

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus as PipelineStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockResult as LockResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockService as LockService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResourceLock as ResourceLock,
)


class TestWorkspaceLockService:
    def test_acquire_lock(self):
        service = LockService()

        result = service.acquire("binding", "binding-1", "pipeline-1")

        assert isinstance(result, LockResult)
        assert result.acquired is True
        assert isinstance(result.lock, ResourceLock)
        assert result.lock.resource_type == "binding"
        assert result.lock.resource_id == "binding-1"
        assert result.lock.pipeline_id == "pipeline-1"
        assert result.lock.expires_at > result.lock.acquired_at

    def test_duplicate_lock_rejection(self):
        service = LockService()

        first = service.acquire("binding", "binding-1", "pipeline-1")

        contested = service.acquire("binding", "binding-1", "pipeline-2")
        assert contested.acquired is False
        assert contested.lock is None
        assert "pipeline-1" in contested.reason

        # The same pipeline re-acquiring its own active lock is idempotent, not rejected.
        reacquired = service.acquire("binding", "binding-1", "pipeline-1")
        assert reacquired.acquired is True
        assert reacquired.lock.lock_id == first.lock.lock_id

    def test_release_lock(self):
        service = LockService()

        result = service.acquire("binding", "binding-1", "pipeline-1")
        assert service.is_locked("binding", "binding-1") is True

        service.release(result.lock.lock_id)

        assert service.is_locked("binding", "binding-1") is False

        with pytest.raises(Error):
            service.release(result.lock.lock_id)

        with pytest.raises(Error):
            service.release("unknown-lock-id")

    def test_expiration_cleanup(self):
        service = LockService()

        service.acquire("binding", "binding-1", "pipeline-1", ttl_seconds=0.1)
        service.acquire("binding", "binding-2", "pipeline-2")

        time.sleep(0.2)

        assert service.is_locked("binding", "binding-1") is False
        assert service.is_locked("binding", "binding-2") is True

        # The resource becomes available for a new pipeline once its lock expires.
        reacquired = service.acquire("binding", "binding-1", "pipeline-3")
        assert reacquired.acquired is True

        removed = service.cleanup_expired()
        assert removed == 0  # nothing left expired: binding-1 was replaced, binding-2 is still active

    def test_active_lock_lookup(self):
        service = LockService()

        assert service.is_locked("binding", "binding-1") is False

        service.acquire("binding", "binding-1", "pipeline-1")

        assert service.is_locked("binding", "binding-1") is True
        assert service.is_locked("binding", "binding-2") is False

        with pytest.raises(Error):
            service.is_locked("   ", "binding-1")

    def test_pipeline_lock_listing(self):
        service = LockService()

        service.acquire("binding", "binding-1", "pipeline-1")
        service.acquire("binding", "binding-2", "pipeline-1")
        service.acquire("binding", "binding-3", "pipeline-2")

        pipeline_1_locks = service.locks("pipeline-1")
        assert {lock.resource_id for lock in pipeline_1_locks} == {"binding-1", "binding-2"}

        pipeline_2_locks = service.locks("pipeline-2")
        assert {lock.resource_id for lock in pipeline_2_locks} == {"binding-3"}

        assert service.locks("pipeline-unknown") == ()

        with pytest.raises(Error):
            service.locks("   ")

    def test_validation_rejections(self):
        with pytest.raises(Error):
            ResourceLock(
                lock_id="l1",
                resource_type="binding",
                resource_id="b1",
                pipeline_id="p1",
                acquired_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            )

        service = LockService()

        with pytest.raises(Error):
            service.acquire("   ", "binding-1", "pipeline-1")

        with pytest.raises(Error):
            service.acquire("binding", "   ", "pipeline-1")

        with pytest.raises(Error):
            service.acquire("binding", "binding-1", "   ")

        with pytest.raises(Error):
            service.acquire("binding", "binding-1", "pipeline-1", ttl_seconds=0)

        with pytest.raises(Error):
            service.acquire("binding", "binding-1", "pipeline-1", ttl_seconds=-5)

    def test_release_locks_after_pipeline_completion(self):
        lock_service = LockService()
        pipeline_service = None
        acquired_locks = []

        def _validation(workspace_id, configuration):
            result = lock_service.acquire("binding", "binding-1", "pipeline-1")
            assert result.acquired is True
            acquired_locks.append(result.lock)

        pipeline_service = PipelineService(stage_executors={"validation": _validation})
        pipeline_service.create(
            Pipeline(
                pipeline_id="pipeline-1",
                workspace_id="workspace-1",
                name="release",
                stages=(Stage(stage_id="stage-1", type="validation", order=0),),
            )
        )

        result = pipeline_service.execute("pipeline-1")
        assert result.status == PipelineStatus.COMPLETED

        assert lock_service.is_locked("binding", "binding-1") is True

        for lock in acquired_locks:
            lock_service.release(lock.lock_id)

        assert lock_service.is_locked("binding", "binding-1") is False
