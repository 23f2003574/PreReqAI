from dataclasses import (
    replace,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding as Binding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService as GroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService as PresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService as BindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService as TemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace as Workspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation as ChangeOperation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetApprovalPolicy as ApprovalPolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetReviewService as ReviewService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetService as ChangeSetService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceConflictService as ConflictService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRequest as DeploymentRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentService as DeploymentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as Service,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus as Status,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeService as MergeService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService as WorkspaceService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidator as Validator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceVersionService as VersionService,
)

from datetime import (
    datetime,
    timezone,
)


def _stage(stage_id, stage_type, order, configuration=None):
    return Stage(
        stage_id=stage_id,
        type=stage_type,
        order=order,
        configuration=configuration if configuration is not None else {},
    )


def _pipeline(pipeline_id, workspace_id, stages, name="release pipeline"):
    return Pipeline(
        pipeline_id=pipeline_id,
        workspace_id=workspace_id,
        name=name,
        stages=stages,
    )


def _tracking_executor(calls, name, result=None):
    def _execute(workspace_id, configuration):
        calls.append(name)
        return result

    return _execute


def _binding(binding_id):
    return Binding(
        binding_id=binding_id,
        profile_id="development",
        capability_id="capability-a",
        created_at=datetime.now(timezone.utc),
    )


def _workspace(workspace_id, binding_ids=()):
    return Workspace(
        workspace_id=workspace_id,
        name=workspace_id,
        description="A workspace.",
        binding_ids=binding_ids,
        template_ids=(),
        preset_ids=(),
        group_ids=(),
    )


def _operation(operation_id, operation_type, resource_type, resource_id):
    return ChangeOperation(
        operation_id=operation_id,
        operation_type=operation_type,
        resource_type=resource_type,
        resource_id=resource_id,
    )


class TestWorkspaceExecutionPipelineService:
    def test_create_pipeline(self):
        service = Service()

        pipeline = _pipeline("pipeline-1", "workspace-1", (_stage("stage-1", "validation", 0),))
        created = service.create(pipeline)

        assert created.status == Status.CREATED
        assert service.status("pipeline-1") == created

    def test_successful_execution(self):
        calls = []

        service = Service(
            stage_executors={
                "validation": _tracking_executor(calls, "validation"),
                "review": _tracking_executor(calls, "review"),
                "merge": _tracking_executor(calls, "merge"),
                "deployment": _tracking_executor(calls, "deployment"),
            }
        )

        stages = (
            _stage("stage-4", "deployment", 3),
            _stage("stage-2", "review", 1),
            _stage("stage-1", "validation", 0),
            _stage("stage-3", "merge", 2),
        )

        service.create(_pipeline("pipeline-1", "workspace-1", stages))

        result = service.execute("pipeline-1")

        assert result.status == Status.COMPLETED
        assert calls == ["validation", "review", "merge", "deployment"]

    def test_pause_and_resume(self):
        calls = []
        service = None

        def _review(workspace_id, configuration):
            calls.append("review")
            service.pause("pipeline-1")

        def _merge(workspace_id, configuration):
            calls.append("merge")

        service = Service(
            stage_executors={
                "validation": _tracking_executor(calls, "validation"),
                "review": _review,
                "merge": _merge,
            }
        )

        stages = (
            _stage("stage-1", "validation", 0),
            _stage("stage-2", "review", 1),
            _stage("stage-3", "merge", 2),
        )

        service.create(_pipeline("pipeline-1", "workspace-1", stages))

        paused = service.execute("pipeline-1")

        assert paused.status == Status.PAUSED
        assert calls == ["validation", "review"]

        with pytest.raises(Error):
            service.execute("pipeline-1")

        resumed = service.resume("pipeline-1")

        assert resumed.status == Status.COMPLETED
        assert calls == ["validation", "review", "merge"]

        with pytest.raises(Error):
            service.resume("pipeline-1")

    def test_cancellation(self):
        calls = []
        service = None

        def _review(workspace_id, configuration):
            calls.append("review")
            service.cancel("pipeline-1")

        def _merge(workspace_id, configuration):
            calls.append("merge")

        service = Service(
            stage_executors={
                "validation": _tracking_executor(calls, "validation"),
                "review": _review,
                "merge": _merge,
            }
        )

        stages = (
            _stage("stage-1", "validation", 0),
            _stage("stage-2", "review", 1),
            _stage("stage-3", "merge", 2),
        )

        service.create(_pipeline("pipeline-1", "workspace-1", stages))

        cancelled = service.execute("pipeline-1")

        assert cancelled.status == Status.CANCELLED
        assert calls == ["validation", "review"]

        with pytest.raises(Error):
            service.resume("pipeline-1")

        with pytest.raises(Error):
            service.cancel("pipeline-1")

        service.create(_pipeline("pipeline-2", "workspace-1", stages))
        fresh_cancel = service.cancel("pipeline-2")

        assert fresh_cancel.status == Status.CANCELLED

    def test_stage_failure_handling(self):
        calls = []

        def _failing_merge(workspace_id, configuration):
            raise RuntimeError("merge conflict")

        service = Service(
            stage_executors={
                "validation": _tracking_executor(calls, "validation"),
                "review": _tracking_executor(calls, "review"),
                "merge": _failing_merge,
                "deployment": _tracking_executor(calls, "deployment"),
            }
        )

        stages = (
            _stage("stage-1", "validation", 0),
            _stage("stage-2", "review", 1),
            _stage("stage-3", "merge", 2),
            _stage("stage-4", "deployment", 3),
        )

        service.create(_pipeline("pipeline-1", "workspace-1", stages))

        with pytest.raises(Error):
            service.execute("pipeline-1")

        assert calls == ["validation", "review"]
        assert service.status("pipeline-1").status == Status.FAILED

        unconfigured_service = Service(stage_executors={})
        unconfigured_service.create(_pipeline("pipeline-2", "workspace-1", (_stage("stage-1", "validation", 0),)))

        with pytest.raises(Error):
            unconfigured_service.execute("pipeline-2")

        assert unconfigured_service.status("pipeline-2").status == Status.FAILED

    def test_execution_status_updates(self):
        service = Service(stage_executors={"validation": lambda workspace_id, configuration: None})

        service.create(_pipeline("pipeline-1", "workspace-1", (_stage("stage-1", "validation", 0),)))

        assert service.status("pipeline-1").status == Status.CREATED

        completed = service.execute("pipeline-1")

        assert completed.status == Status.COMPLETED
        assert service.status("pipeline-1").status == Status.COMPLETED

        with pytest.raises(Error):
            service.status("   ")

        with pytest.raises(Error):
            service.status("unknown-pipeline")

    def test_invalid_pipeline_rejection(self):
        with pytest.raises(Error):
            _stage("   ", "validation", 0)

        with pytest.raises(Error):
            _stage("stage-1", "not_a_real_type", 0)

        with pytest.raises(Error):
            _pipeline("   ", "workspace-1", (_stage("stage-1", "validation", 0),))

        with pytest.raises(Error):
            _pipeline("pipeline-1", "   ", (_stage("stage-1", "validation", 0),))

        with pytest.raises(Error):
            _pipeline("pipeline-1", "workspace-1", ())

        with pytest.raises(Error):
            _pipeline(
                "pipeline-1",
                "workspace-1",
                (
                    _stage("stage-1", "validation", 0),
                    _stage("stage-2", "review", 0),
                ),
            )

        service = Service()

        with pytest.raises(Error):
            service.create(None)

        pipeline = _pipeline("pipeline-1", "workspace-1", (_stage("stage-1", "validation", 0),))
        service.create(pipeline)

        with pytest.raises(Error):
            service.create(pipeline)

    def test_integrates_with_validation_review_merge_and_deployment_services(self):
        binding_service = BindingRegistryService()
        template_service = TemplateRegistryService()
        preset_service = PresetRegistryService()
        group_service = GroupRegistryService()

        binding_service.register(_binding("binding-1"))

        workspace_service = WorkspaceService(binding_service, template_service, preset_service, group_service)
        workspace_service.create(_workspace("workspace-1"))

        version_service = VersionService(workspace_service)
        change_set_service = ChangeSetService(workspace_service)
        policy = ApprovalPolicy(minimum_approvals=1, require_unanimous=False)
        review_service = ReviewService(change_set_service, policy)
        conflict_service = ConflictService(change_set_service, workspace_service)
        merge_service = MergeService(change_set_service, review_service, conflict_service)
        validator = Validator(binding_service, template_service, preset_service, group_service)
        deployment_service = DeploymentService(
            version_service,
            workspace_service,
            binding_service,
            template_service,
            preset_service,
            group_service,
        )

        change_set = change_set_service.create("workspace-1", "add binding-1")
        change_set = change_set_service.add_operation(
            change_set.change_set_id, _operation("op-1", "add", "binding", "binding-1")
        )

        def _validate(workspace_id, configuration):
            result = validator.validate(workspace_service.find(workspace_id))

            if not result.valid:
                raise RuntimeError(f"workspace {workspace_id!r} failed validation: {result.violations}")

        def _review(workspace_id, configuration):
            review = review_service.submit(configuration["change_set_id"], "reviewer-a")
            review_service.approve(review.review_id)

        def _merge(workspace_id, configuration):
            result = merge_service.merge(configuration["change_set_ids"])

            if not result.successful:
                raise RuntimeError(f"merge blocked by conflicts: {result.conflicts_detected}")

        def _deploy(workspace_id, configuration):
            version_service.publish(workspace_id, configuration["version"])
            deployment_service.deploy(
                DeploymentRequest(
                    workspace_id=workspace_id,
                    version=configuration["version"],
                    target_environment=configuration["target_environment"],
                )
            )

        service = Service(
            stage_executors={
                "validation": _validate,
                "review": _review,
                "merge": _merge,
                "deployment": _deploy,
            }
        )

        stages = (
            _stage("stage-1", "validation", 0),
            _stage("stage-2", "review", 1, {"change_set_id": change_set.change_set_id}),
            _stage("stage-3", "merge", 2, {"change_set_ids": [change_set.change_set_id]}),
            _stage("stage-4", "deployment", 3, {"version": "v1", "target_environment": "staging"}),
        )

        service.create(_pipeline("pipeline-1", "workspace-1", stages, name="workspace-1 release"))

        result = service.execute("pipeline-1")

        assert result.status == Status.COMPLETED

        deployment = deployment_service.deployment("workspace-1")

        assert deployment.successful is True
