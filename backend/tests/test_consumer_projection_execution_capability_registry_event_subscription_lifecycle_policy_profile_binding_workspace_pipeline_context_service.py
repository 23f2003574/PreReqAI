import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus as PipelineStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineContextService as ContextService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineContextSnapshot as Snapshot,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContext as Context,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
)


class TestWorkspacePipelineContextService:
    def test_create_context(self):
        service = ContextService()

        context = service.create("pipeline-1")

        assert isinstance(context, Context)
        assert context.pipeline_id == "pipeline-1"
        assert context.variables == {}
        assert context.metadata == {}

        with pytest.raises(Error):
            service.create("pipeline-1")

        with pytest.raises(Error):
            service.create("   ")

    def test_store_and_read_variables(self):
        service = ContextService()
        context = service.create("pipeline-1")

        updated = service.put(context.context_id, "attempt_count", 1)
        assert updated.variables["attempt_count"] == 1

        service.put(context.context_id, "reviewer", "alice")

        fetched = service.get(context.context_id)
        assert fetched.variables == {"attempt_count": 1, "reviewer": "alice"}

        with pytest.raises(Error):
            service.put(context.context_id, "not a valid key", 1)

        with pytest.raises(Error):
            service.put(context.context_id, "", 1)

        with pytest.raises(Error):
            service.put("unknown-context", "key", 1)

        with pytest.raises(Error):
            service.get("unknown-context")

    def test_snapshot_and_restore(self):
        service = ContextService()
        context = service.create("pipeline-1")

        service.put(context.context_id, "count", 1)
        snapshot = service.snapshot(context.context_id, stage_id="stage-1")

        assert isinstance(snapshot, Snapshot)
        assert snapshot.context_id == context.context_id
        assert snapshot.stage_id == "stage-1"
        assert snapshot.variables == {"count": 1}

        service.put(context.context_id, "count", 2)
        service.put(context.context_id, "extra", "value")
        assert service.get(context.context_id).variables == {"count": 2, "extra": "value"}

        restored = service.restore(snapshot.snapshot_id)
        assert restored.variables == {"count": 1}
        assert service.get(context.context_id).variables == {"count": 1}

        # the snapshot itself never changes, even as the live context keeps changing
        service.put(context.context_id, "count", 3)
        assert snapshot.variables == {"count": 1}

    def test_remove_context(self):
        service = ContextService()
        context = service.create("pipeline-1")

        service.remove(context.context_id)

        with pytest.raises(Error):
            service.get(context.context_id)

        with pytest.raises(Error):
            service.remove(context.context_id)

        # the pipeline ID is free to create a new context again
        recreated = service.create("pipeline-1")
        assert recreated.context_id != context.context_id

    def test_invalid_snapshot_rejection(self):
        service = ContextService()
        context = service.create("pipeline-1")

        with pytest.raises(Error):
            service.restore("unknown-snapshot-id")

        with pytest.raises(Error):
            service.restore("   ")

        snapshot = service.snapshot(context.context_id)
        service.remove(context.context_id)

        with pytest.raises(Error):
            service.restore(snapshot.snapshot_id)

    def test_context_isolation(self):
        service = ContextService()

        context_1 = service.create("pipeline-1")
        context_2 = service.create("pipeline-2")

        service.put(context_1.context_id, "shared_key", "from-pipeline-1")
        service.put(context_2.context_id, "shared_key", "from-pipeline-2")

        assert service.get(context_1.context_id).variables["shared_key"] == "from-pipeline-1"
        assert service.get(context_2.context_id).variables["shared_key"] == "from-pipeline-2"

        service.put(context_1.context_id, "only_in_one", True)
        assert "only_in_one" not in service.get(context_2.context_id).variables

    def test_pipeline_stage_to_stage_propagation(self):
        context_service = ContextService()
        pipeline_service = None
        context = context_service.create("pipeline-1")

        def _validation(workspace_id, configuration):
            context_service.put(context.context_id, "validated_at_stage", "stage-1")

        def _review(workspace_id, configuration):
            propagated = context_service.get(context.context_id)
            assert propagated.variables["validated_at_stage"] == "stage-1"
            context_service.snapshot(context.context_id, stage_id="stage-2")

        pipeline_service = PipelineService(
            stage_executors={"validation": _validation, "review": _review}
        )

        stages = (
            Stage(stage_id="stage-1", type="validation", order=0),
            Stage(stage_id="stage-2", type="review", order=1),
        )

        pipeline_service.create(
            Pipeline(pipeline_id="pipeline-1", workspace_id="workspace-1", name="release", stages=stages)
        )

        result = pipeline_service.execute("pipeline-1")

        assert result.status == PipelineStatus.COMPLETED
        assert context_service.get(context.context_id).variables["validated_at_stage"] == "stage-1"
