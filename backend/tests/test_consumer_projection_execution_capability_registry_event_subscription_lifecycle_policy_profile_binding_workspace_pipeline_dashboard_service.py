import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardEntry as Entry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardService as DashboardService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardSummary as Summary,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityService as ObservabilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueService as QueueService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
)


def _build(stage_executors=None, concurrency_limit=5):
    queue_service = QueueService(concurrency_limit=concurrency_limit)
    observability_service = ObservabilityService()
    pipeline_service = PipelineService(
        stage_executors=stage_executors if stage_executors is not None else {"validation": lambda w, c: None}
    )
    dashboard = DashboardService(pipeline_service, queue_service, observability_service)
    return pipeline_service, queue_service, observability_service, dashboard


def _create_pipeline(pipeline_service, pipeline_id):
    pipeline_service.create(
        Pipeline(
            pipeline_id=pipeline_id,
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )


class TestWorkspacePipelineDashboardService:
    def test_dashboard_summary(self):
        pipeline_service, queue_service, observability_service, dashboard = _build()

        _create_pipeline(pipeline_service, "pipeline-1")
        queue_service.enqueue("pipeline-1", priority=1)

        summary = dashboard.summary()

        assert isinstance(summary, Summary)
        assert summary.queued == 1
        assert summary.active == 0
        assert summary.completed == 0
        assert summary.failed == 0

        item = queue_service.dequeue()
        assert dashboard.summary().active == 1

        pipeline_service.execute(item.pipeline_id)
        queue_service.complete(item.queue_item_id, successful=True)

        assert dashboard.summary().completed == 1
        assert dashboard.summary().active == 0

    def test_active_pipeline_query(self):
        _pipeline_service, _queue_service, observability_service, dashboard = _build()

        assert dashboard.active() == ()

        trace = observability_service.begin_trace("pipeline-1", "stage-1")
        active = dashboard.active()

        assert len(active) == 1
        assert isinstance(active[0], Entry)
        assert active[0].pipeline_id == "pipeline-1"
        assert active[0].current_stage == "stage-1"
        assert active[0].started_at == trace.started_at

        observability_service.finish_trace(trace.trace_id, successful=True)
        assert dashboard.active() == ()

    def test_queue_query(self):
        _pipeline_service, queue_service, _observability_service, dashboard = _build()

        assert dashboard.queue() == ()

        queue_service.enqueue("pipeline-1", priority=1)
        queue_service.enqueue("pipeline-2", priority=5)

        queued = dashboard.queue()

        assert len(queued) == 1
        assert queued[0].pipeline_id == "pipeline-2"  # higher priority is next
        assert queued[0].status == "queued"
        assert queued[0].current_stage is None

    def test_history_ordering(self):
        pipeline_service, _queue_service, _observability_service, dashboard = _build()

        _create_pipeline(pipeline_service, "pipeline-1")
        _create_pipeline(pipeline_service, "pipeline-2")

        pipeline_service.execute("pipeline-1")
        dashboard.pipeline("pipeline-1")  # observed first

        pipeline_service.execute("pipeline-2")
        dashboard.pipeline("pipeline-2")  # observed second

        history = dashboard.history(10)

        assert [entry.pipeline_id for entry in history] == ["pipeline-2", "pipeline-1"]

        limited = dashboard.history(1)
        assert [entry.pipeline_id for entry in limited] == ["pipeline-2"]

    def test_pipeline_lookup(self):
        pipeline_service, _queue_service, _observability_service, dashboard = _build()

        _create_pipeline(pipeline_service, "pipeline-1")
        pipeline_service.execute("pipeline-1")

        entry = dashboard.pipeline("pipeline-1")

        assert isinstance(entry, Entry)
        assert entry.pipeline_id == "pipeline-1"
        assert entry.status == "completed"
        assert entry.progress == 1.0

        with pytest.raises(Error):
            dashboard.pipeline("unknown-pipeline")

        with pytest.raises(Error):
            dashboard.pipeline("   ")

    def test_invalid_limit_rejection(self):
        _pipeline_service, _queue_service, _observability_service, dashboard = _build()

        with pytest.raises(Error):
            dashboard.history(0)

        with pytest.raises(Error):
            dashboard.history(-1)

        with pytest.raises(Error):
            dashboard.history("not_an_int")

        with pytest.raises(Error):
            dashboard.history(None)
