import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus as PipelineStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCondition as Condition,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGate as Gate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateService as GateService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineGateStatus as GateStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
)


def _condition(condition_id, stage_id, expression, failure_action="block"):
    return Condition(
        condition_id=condition_id,
        stage_id=stage_id,
        expression=expression,
        failure_action=failure_action,
    )


def _gate(gate_id, stage_id, gate_type, mandatory=True):
    return Gate(
        gate_id=gate_id,
        stage_id=stage_id,
        gate_type=gate_type,
        mandatory=mandatory,
    )


class TestWorkspacePipelineGateService:
    def test_condition_evaluation(self):
        service = GateService()

        service.register_condition(_condition("cond-1", "stage-1", "count >= 3", failure_action="block"))

        assert service.evaluate("stage-1", {"count": 1}) is False
        assert service.evaluate("stage-1", {"count": 5}) is True

        service.register_condition(
            _condition("cond-2", "stage-2", "status == \'ready\'", failure_action="fail")
        )

        assert service.evaluate("stage-2", {"status": "ready"}) is True

        with pytest.raises(Error):
            service.evaluate("stage-2", {"status": "not-ready"})

        service.register_condition(_condition("cond-3", "stage-3", "optional_flag", failure_action="skip"))

        assert service.evaluate("stage-3", {"optional_flag": False}) is True

    def test_gate_blocking(self):
        service = GateService()

        service.register_gate(_gate("gate-1", "stage-1", "manual"), "pipeline-1")

        assert service.evaluate("stage-1") is False

        closed = service.close("gate-1")
        assert closed.status == GateStatus.CLOSED
        assert service.evaluate("stage-1") is False

        assert service.evaluate("stage-with-no-gate") is True

    def test_manual_approval(self):
        service = GateService()

        service.register_gate(_gate("gate-1", "stage-1", "manual"), "pipeline-1")

        assert service.evaluate("stage-1") is False

        opened = service.open("gate-1")

        assert opened.status == GateStatus.OPEN
        assert service.evaluate("stage-1") is True

        with pytest.raises(Error):
            service.open("gate-1")

        with pytest.raises(Error):
            service.close("gate-1")

    def test_automatic_approval(self):
        service = GateService()

        service.register_gate(_gate("gate-1", "stage-1", "automatic"), "pipeline-1")

        pending_before = service.pending("pipeline-1")
        assert [gate.gate_id for gate in pending_before] == ["gate-1"]
        assert pending_before[0].status == GateStatus.PENDING

        assert service.evaluate("stage-1") is True

        assert service.pending("pipeline-1") == ()

    def test_bypass_rejection(self):
        service = GateService()

        service.register_gate(_gate("gate-1", "stage-1", "manual", mandatory=True), "pipeline-1")
        service.register_gate(_gate("gate-2", "stage-2", "manual", mandatory=False), "pipeline-1")

        with pytest.raises(Error):
            service.bypass("gate-1")

        bypassed = service.bypass("gate-2")

        assert bypassed.status == GateStatus.BYPASSED
        assert service.evaluate("stage-2") is True

        with pytest.raises(Error):
            service.bypass("gate-2")

    def test_pending_gate_lookup(self):
        service = GateService()

        service.register_gate(_gate("gate-1", "stage-1", "manual"), "pipeline-1")
        service.register_gate(_gate("gate-2", "stage-2", "manual"), "pipeline-1")
        service.register_gate(_gate("gate-3", "stage-3", "manual"), "pipeline-2")

        pending_for_1 = service.pending("pipeline-1")
        assert {gate.gate_id for gate in pending_for_1} == {"gate-1", "gate-2"}

        service.open("gate-1")

        pending_for_1 = service.pending("pipeline-1")
        assert {gate.gate_id for gate in pending_for_1} == {"gate-2"}

        pending_for_2 = service.pending("pipeline-2")
        assert [gate.gate_id for gate in pending_for_2] == ["gate-3"]
        assert service.pending("pipeline-unknown") == ()

        with pytest.raises(Error):
            service.pending("   ")

    def test_validation_rejections(self):
        with pytest.raises(Error):
            _condition("   ", "stage-1", "count >= 1")

        with pytest.raises(Error):
            _condition("cond-1", "stage-1", "__import__(\'os\').system(\'ls\')")

        with pytest.raises(Error):
            _condition("cond-1", "stage-1", "count >=")

        with pytest.raises(Error):
            _gate("   ", "stage-1", "manual")

        with pytest.raises(Error):
            _gate("gate-1", "stage-1", "not_a_real_type")

        service = GateService()
        service.register_gate(_gate("gate-1", "stage-1", "manual"), "pipeline-1")

        with pytest.raises(Error):
            service.register_gate(_gate("gate-2", "stage-1", "manual"), "pipeline-1")

        with pytest.raises(Error):
            service.evaluate("   ")

        with pytest.raises(Error):
            service.register_condition(None)

        with pytest.raises(Error):
            service.register_gate(None, "pipeline-1")

    def test_pipeline_resumes_after_approval(self):
        gate_service = GateService()
        gate_service.register_gate(_gate("gate-1", "stage-2", "manual"), "pipeline-1")

        pipeline_service = None
        calls = []

        def _validate(workspace_id, configuration):
            calls.append("validation")

        def _review(workspace_id, configuration):
            calls.append("review")

            if not gate_service.evaluate("stage-2"):
                pipeline_service.pause("pipeline-1")

        def _merge(workspace_id, configuration):
            calls.append("merge")

        pipeline_service = PipelineService(
            stage_executors={
                "validation": _validate,
                "review": _review,
                "merge": _merge,
            }
        )

        stages = (
            Stage(stage_id="stage-1", type="validation", order=0),
            Stage(stage_id="stage-2", type="review", order=1),
            Stage(stage_id="stage-3", type="merge", order=2),
        )

        pipeline_service.create(
            Pipeline(pipeline_id="pipeline-1", workspace_id="workspace-1", name="release", stages=stages)
        )

        paused = pipeline_service.execute("pipeline-1")

        assert paused.status == PipelineStatus.PAUSED
        assert calls == ["validation", "review"]
        assert gate_service.pending("pipeline-1") != ()

        gate_service.open("gate-1")

        resumed = pipeline_service.resume("pipeline-1")

        assert resumed.status == PipelineStatus.COMPLETED
        assert calls == ["validation", "review", "merge"]
        assert gate_service.pending("pipeline-1") == ()
