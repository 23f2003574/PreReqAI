import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus as PipelineStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItem as Item,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus as ItemStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueService as QueueService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueStatistics as Statistics,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
)


class TestWorkspacePipelineQueueService:
    def test_enqueue_dequeue(self):
        service = QueueService()

        item = service.enqueue("pipeline-1", 1)

        assert isinstance(item, Item)
        assert item.pipeline_id == "pipeline-1"
        assert item.status == ItemStatus.QUEUED

        dequeued = service.dequeue()

        assert dequeued.queue_item_id == item.queue_item_id
        assert dequeued.status == ItemStatus.RUNNING

        assert service.dequeue() is None  # concurrency_limit=1, one already running

    def test_priority_ordering(self):
        service = QueueService(concurrency_limit=10)

        service.enqueue("pipeline-low", 1)
        service.enqueue("pipeline-high", 9)
        service.enqueue("pipeline-medium", 5)

        first = service.dequeue()
        second = service.dequeue()
        third = service.dequeue()

        assert [item.pipeline_id for item in (first, second, third)] == [
            "pipeline-high",
            "pipeline-medium",
            "pipeline-low",
        ]

    def test_fifo_ordering(self):
        service = QueueService(concurrency_limit=10)

        service.enqueue("pipeline-a", 5)
        service.enqueue("pipeline-b", 5)
        service.enqueue("pipeline-c", 5)

        order = [service.dequeue().pipeline_id for _ in range(3)]

        assert order == ["pipeline-a", "pipeline-b", "pipeline-c"]

    def test_duplicate_enqueue_rejection(self):
        service = QueueService(concurrency_limit=10)

        service.enqueue("pipeline-1", 1)

        with pytest.raises(Error):
            service.enqueue("pipeline-1", 5)

        running = service.dequeue()

        with pytest.raises(Error):
            service.enqueue("pipeline-1", 5)

        service.complete(running.queue_item_id)

        # Once completed, the pipeline ID is eligible to be queued again.
        requeued = service.enqueue("pipeline-1", 3)
        assert requeued.pipeline_id == "pipeline-1"

    def test_statistics_generation(self):
        service = QueueService(concurrency_limit=10)

        service.enqueue("pipeline-1", 1)
        item_2 = service.enqueue("pipeline-2", 1)
        item_3 = service.enqueue("pipeline-3", 1)

        service.dequeue()  # pipeline-1 -> running

        stats = service.statistics()
        assert isinstance(stats, Statistics)
        assert stats.queued == 2
        assert stats.running == 1
        assert stats.completed == 0
        assert stats.failed == 0

        running_2 = service.dequeue()
        service.complete(running_2.queue_item_id, successful=True)

        running_3 = service.dequeue()
        service.complete(running_3.queue_item_id, successful=False)

        stats = service.statistics()
        assert stats.completed == 1
        assert stats.failed == 1

    def test_clear_completed_items(self):
        service = QueueService(concurrency_limit=10)

        item_1 = service.enqueue("pipeline-1", 1)
        service.enqueue("pipeline-2", 1)

        service.dequeue()
        service.complete(item_1.queue_item_id, successful=True)

        removed = service.clear_completed()
        assert removed == 1

        stats = service.statistics()
        assert stats.completed == 0
        assert stats.queued == 1

        # A cleared pipeline ID becomes eligible to be queued again.
        service.enqueue("pipeline-1", 1)

    def test_validation_rejections(self):
        with pytest.raises(Error):
            QueueService(concurrency_limit=0)

        with pytest.raises(Error):
            QueueService(concurrency_limit=-1)

        service = QueueService()

        with pytest.raises(Error):
            service.enqueue("   ", 1)

        with pytest.raises(Error):
            service.enqueue("pipeline-1", -1)

        with pytest.raises(Error):
            service.enqueue("pipeline-1", "not_an_int")

        with pytest.raises(Error):
            service.complete("unknown-item")

        with pytest.raises(Error):
            service.complete("   ")

    def test_peek_does_not_mutate_state(self):
        service = QueueService()

        service.enqueue("pipeline-1", 1)

        peeked_first = service.peek()
        peeked_second = service.peek()

        assert peeked_first == peeked_second
        assert peeked_first.status == ItemStatus.QUEUED

        assert service.statistics().queued == 1
        assert service.statistics().running == 0

    def test_integrates_with_execution_pipeline_service(self):
        queue_service = QueueService(concurrency_limit=1)
        pipeline_service = PipelineService(
            stage_executors={"validation": lambda workspace_id, configuration: None}
        )

        for pipeline_id in ("pipeline-1", "pipeline-2"):
            pipeline_service.create(
                Pipeline(
                    pipeline_id=pipeline_id,
                    workspace_id="workspace-1",
                    name="release",
                    stages=(Stage(stage_id="stage-1", type="validation", order=0),),
                )
            )
            queue_service.enqueue(pipeline_id, priority=1)

        item = queue_service.dequeue()
        result = pipeline_service.execute(item.pipeline_id)
        queue_service.complete(item.queue_item_id, successful=result.status == PipelineStatus.COMPLETED)

        assert result.status == PipelineStatus.COMPLETED

        next_item = queue_service.dequeue()
        assert next_item.pipeline_id == "pipeline-2"
