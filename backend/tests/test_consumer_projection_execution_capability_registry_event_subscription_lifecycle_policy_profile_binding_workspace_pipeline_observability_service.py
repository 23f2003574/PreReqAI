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
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDiagnosticReport as DiagnosticReport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionTrace as Trace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityService as ObservabilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
)


class TestWorkspacePipelineObservabilityService:
    def test_begin_finish_trace(self):
        service = ObservabilityService()

        trace = service.begin_trace("pipeline-1", "stage-1")

        assert isinstance(trace, Trace)
        assert trace.status == "running"
        assert trace.finished_at is None

        finished = service.finish_trace(trace.trace_id, successful=True)

        assert finished.trace_id == trace.trace_id
        assert finished.status == "succeeded"
        assert finished.finished_at is not None
        assert finished.finished_at >= finished.started_at

        with pytest.raises(Error):
            service.begin_trace("   ", "stage-1")

        with pytest.raises(Error):
            service.finish_trace("   ")

    def test_duration_calculation(self):
        service = ObservabilityService()

        trace = service.begin_trace("pipeline-1", "stage-1")
        time.sleep(0.05)
        service.finish_trace(trace.trace_id)

        report = service.report("pipeline-1")

        assert report.duration >= 0.05
        assert report.duration < 5  # sanity bound, not a flaky tight tolerance

    def test_diagnostic_report(self):
        service = ObservabilityService()

        succeeded = service.begin_trace("pipeline-1", "stage-1")
        service.finish_trace(succeeded.trace_id, successful=True)

        failed = service.begin_trace("pipeline-1", "stage-2")
        service.finish_trace(failed.trace_id, successful=False)

        report = service.report("pipeline-1")

        assert isinstance(report, DiagnosticReport)
        assert report.pipeline_id == "pipeline-1"
        assert report.failed_stage == "stage-2"
        assert report.warnings == ()

        with pytest.raises(Error):
            service.report("pipeline-with-no-traces")

    def test_active_trace_listing(self):
        service = ObservabilityService()

        assert service.active_traces() == ()

        running = service.begin_trace("pipeline-1", "stage-1")
        finished = service.begin_trace("pipeline-1", "stage-2")
        service.finish_trace(finished.trace_id)

        active = service.active_traces()
        assert [trace.trace_id for trace in active] == [running.trace_id]

        report = service.report("pipeline-1")
        assert report.warnings == ("Stage ID 'stage-1' has not finished.",)

    def test_duplicate_trace_rejection(self):
        service = ObservabilityService()

        trace = service.begin_trace("pipeline-1", "stage-1")

        with pytest.raises(Error):
            service.begin_trace("pipeline-1", "stage-1")

        service.finish_trace(trace.trace_id)

        # A new trace for the same stage is fine once the prior one has finished.
        retried = service.begin_trace("pipeline-1", "stage-1")
        assert retried.trace_id != trace.trace_id

    def test_purge_old_traces(self):
        service = ObservabilityService()

        old_trace = service.begin_trace("pipeline-1", "stage-old")
        service.finish_trace(old_trace.trace_id)

        still_running = service.begin_trace("pipeline-1", "stage-running")

        cutoff = datetime.now(timezone.utc) + timedelta(seconds=10)
        removed = service.purge(cutoff)

        # the finished trace is removed, the still-running trace survives regardless of age
        assert removed == 1
        assert [trace.trace_id for trace in service.active_traces()] == [still_running.trace_id]

        with pytest.raises(Error):
            service.purge(None)

    def test_pipeline_traces_stage_lifecycle(self):
        observability_service = ObservabilityService()
        recorded_trace_ids = []

        def _validation(workspace_id, configuration):
            trace = observability_service.begin_trace("pipeline-1", "stage-1")
            recorded_trace_ids.append(trace.trace_id)
            observability_service.finish_trace(trace.trace_id, successful=True)

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
        assert len(recorded_trace_ids) == 1

        report = observability_service.report("pipeline-1")
        assert report.failed_stage is None
