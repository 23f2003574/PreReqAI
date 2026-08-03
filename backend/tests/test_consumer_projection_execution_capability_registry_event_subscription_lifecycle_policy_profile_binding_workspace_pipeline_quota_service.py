import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaResult as QuotaResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaService as QuotaService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueService as QueueService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget as Budget,
)


def _budget(budget_id, pipeline_id, max_runtime=10, max_memory=100, max_parallel_tasks=1):
    return Budget(
        budget_id=budget_id,
        pipeline_id=pipeline_id,
        max_runtime=max_runtime,
        max_memory=max_memory,
        max_parallel_tasks=max_parallel_tasks,
    )


class TestWorkspacePipelineQuotaService:
    def test_reserve_release_budget(self):
        service = QuotaService(max_runtime=100, max_memory=1000, max_parallel_tasks=5)
        service.register(_budget("budget-1", "pipeline-1", max_runtime=20, max_memory=200, max_parallel_tasks=2))

        result = service.reserve("pipeline-1")

        assert isinstance(result, QuotaResult)
        assert result.accepted is True
        assert result.remaining_budget == {"max_runtime": 80, "max_memory": 800, "max_parallel_tasks": 3}
        assert service.usage("pipeline-1").budget_id == "budget-1"

        service.release("pipeline-1")

        assert service.usage("pipeline-1") is None
        assert dict(service.remaining()) == {"max_runtime": 100, "max_memory": 1000, "max_parallel_tasks": 5}

        with pytest.raises(Error):
            service.release("pipeline-1")

    def test_quota_validation(self):
        service = QuotaService(max_runtime=100, max_memory=1000, max_parallel_tasks=5)
        service.register(_budget("budget-1", "pipeline-1", max_runtime=20, max_memory=200, max_parallel_tasks=2))

        result = service.validate("pipeline-1")
        assert result.accepted is True

        # validate() does not reserve
        assert service.usage("pipeline-1") is None
        assert dict(service.remaining()) == {"max_runtime": 100, "max_memory": 1000, "max_parallel_tasks": 5}

        with pytest.raises(Error):
            service.validate("unregistered-pipeline")

    def test_usage_tracking(self):
        service = QuotaService(max_runtime=100, max_memory=1000, max_parallel_tasks=5)
        service.register(_budget("budget-1", "pipeline-1", max_runtime=20, max_memory=200, max_parallel_tasks=2))
        service.register(_budget("budget-2", "pipeline-2", max_runtime=30, max_memory=300, max_parallel_tasks=1))

        assert service.usage("pipeline-1") is None

        service.reserve("pipeline-1")
        assert service.usage("pipeline-1").pipeline_id == "pipeline-1"
        assert service.usage("pipeline-2") is None

        service.reserve("pipeline-2")
        assert service.usage("pipeline-2").pipeline_id == "pipeline-2"

    def test_duplicate_reservation_rejection(self):
        service = QuotaService(max_runtime=100, max_memory=1000, max_parallel_tasks=5)
        service.register(_budget("budget-1", "pipeline-1", max_runtime=20, max_memory=200, max_parallel_tasks=2))

        service.reserve("pipeline-1")

        with pytest.raises(Error):
            service.reserve("pipeline-1")

        service.release("pipeline-1")
        second = service.reserve("pipeline-1")
        assert second.accepted is True

    def test_quota_exceeded_rejection(self):
        service = QuotaService(max_runtime=50, max_memory=500, max_parallel_tasks=2)
        service.register(_budget("budget-1", "pipeline-1", max_runtime=40, max_memory=400, max_parallel_tasks=2))
        service.register(_budget("budget-2", "pipeline-2", max_runtime=20, max_memory=200, max_parallel_tasks=1))

        first = service.reserve("pipeline-1")
        assert first.accepted is True

        second = service.reserve("pipeline-2")
        assert second.accepted is False
        assert "exceeds remaining" in second.reason
        assert service.usage("pipeline-2") is None

        # the pool was left untouched by the rejected reservation
        assert dict(service.remaining()) == {"max_runtime": 10, "max_memory": 100, "max_parallel_tasks": 0}

    def test_remaining_budget_calculation(self):
        service = QuotaService(max_runtime=100, max_memory=1000, max_parallel_tasks=5)
        service.register(_budget("budget-1", "pipeline-1", max_runtime=20, max_memory=200, max_parallel_tasks=2))
        service.register(_budget("budget-2", "pipeline-2", max_runtime=30, max_memory=300, max_parallel_tasks=1))

        assert dict(service.remaining()) == {"max_runtime": 100, "max_memory": 1000, "max_parallel_tasks": 5}

        service.reserve("pipeline-1")
        assert dict(service.remaining()) == {"max_runtime": 80, "max_memory": 800, "max_parallel_tasks": 3}

        service.reserve("pipeline-2")
        assert dict(service.remaining()) == {"max_runtime": 50, "max_memory": 500, "max_parallel_tasks": 2}

        service.release("pipeline-1")
        assert dict(service.remaining()) == {"max_runtime": 70, "max_memory": 700, "max_parallel_tasks": 4}

    def test_validation_rejections(self):
        with pytest.raises(Error):
            _budget("budget-1", "pipeline-1", max_runtime=-1)

        with pytest.raises(Error):
            _budget("budget-1", "pipeline-1", max_memory=-1)

        with pytest.raises(Error):
            _budget("budget-1", "pipeline-1", max_parallel_tasks=-1)

        with pytest.raises(Error):
            _budget("   ", "pipeline-1")

        with pytest.raises(Error):
            QuotaService(max_runtime=-1, max_memory=100, max_parallel_tasks=1)

        service = QuotaService(max_runtime=100, max_memory=1000, max_parallel_tasks=5)

        with pytest.raises(Error):
            service.reserve("   ")

        with pytest.raises(Error):
            service.reserve("pipeline-without-budget")

        service.register(_budget("budget-1", "pipeline-1"))

        with pytest.raises(Error):
            service.register(_budget("budget-1", "pipeline-2"))  # duplicate budget ID

        with pytest.raises(Error):
            service.register(_budget("budget-2", "pipeline-1"))  # pipeline already has a budget

    def test_integrates_with_execution_queue(self):
        quota_service = QuotaService(max_runtime=100, max_memory=1000, max_parallel_tasks=5)
        queue_service = QueueService(concurrency_limit=10)

        quota_service.register(_budget("budget-1", "pipeline-1", max_runtime=20, max_memory=200, max_parallel_tasks=2))

        reservation = quota_service.reserve("pipeline-1")
        assert reservation.accepted is True

        queue_service.enqueue("pipeline-1", priority=1)
        item = queue_service.dequeue()

        queue_service.complete(item.queue_item_id, successful=True)
        quota_service.release("pipeline-1")

        assert quota_service.usage("pipeline-1") is None
