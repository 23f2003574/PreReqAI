import dataclasses

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackService,
)


def _binding(binding_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id="development",
        capability_id=f"capability-{binding_id}",
        created_at=datetime.now(timezone.utc),
    )


def _record(deployment_id, workspace_id, environment, version, deployed_at, deployed_resources=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRecord(
        deployment_id=deployment_id,
        workspace_id=workspace_id,
        environment=environment,
        version=version,
        deployed_resources=deployed_resources if deployed_resources is not None else {},
        deployed_at=deployed_at,
        status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentStatus.SUCCEEDED,
    )


def _build_context(binding_ids=("binding-1", "binding-2", "binding-3")):
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    for binding_id in binding_ids:
        binding_registry.register(_binding(binding_id))

    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    history_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentHistoryService()

    rollback_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackService(
        history_service,
        binding_registry,
        template_registry,
        preset_registry,
        group_registry,
    )

    return rollback_service, history_service, binding_registry, template_registry, preset_registry, group_registry


class TestSuccessfulRollback:
    def test_successful_rollback(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(
            _record("deployment-1", "workspace-1", "production", "v1", base, deployed_resources={"bindings": ("binding-1",)})
        )
        history_service.record(
            _record(
                "deployment-2",
                "workspace-1",
                "production",
                "v2",
                base + timedelta(minutes=5),
                deployed_resources={"bindings": ("binding-1", "binding-2")},
            )
        )

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
            workspace_id="workspace-1",
            deployment_id="deployment-1",
        )

        result = rollback_service.rollback(request)

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackResult)
        assert result.successful is True
        assert result.previous_deployment.deployment_id == "deployment-2"
        assert result.restored_deployment.version == "v1"
        assert result.restored_deployment.environment == "production"


class TestRollbackEligibility:
    def test_rollback_eligibility(self):
        rollback_service, history_service, *_ = _build_context()

        assert rollback_service.can_rollback("workspace-1") is False

        history_service.record(_record("deployment-1", "workspace-1", "production", "v1", datetime.now(timezone.utc)))
        assert rollback_service.can_rollback("workspace-1") is False

        history_service.record(_record("deployment-2", "workspace-1", "production", "v2", datetime.now(timezone.utc)))
        assert rollback_service.can_rollback("workspace-1") is True

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            rollback_service.can_rollback("   ")


class TestRollbackHistory:
    def test_rollback_history(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "workspace-1", "production", "v1", base)
        second = _record("deployment-2", "workspace-1", "production", "v2", base + timedelta(minutes=5))

        history_service.record(first)
        history_service.record(second)

        assert rollback_service.rollback_history("workspace-1") == (first, second)


class TestRestoredResourcesVerified:
    def test_restored_resources_match_target_deployment(self):
        rollback_service, history_service, binding_registry, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(
            _record("deployment-1", "workspace-1", "production", "v1", base, deployed_resources={"bindings": ("binding-1", "binding-2")})
        )
        history_service.record(
            _record("deployment-2", "workspace-1", "production", "v2", base + timedelta(minutes=5), deployed_resources={"bindings": ("binding-3",)})
        )

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
            workspace_id="workspace-1",
            deployment_id="deployment-1",
        )

        result = rollback_service.rollback(request)

        assert result.restored_resources["bindings"] == ("binding-1", "binding-2")
        assert result.restored_resources == result.restored_deployment.deployed_resources

        for binding_id in result.restored_resources["bindings"]:
            assert binding_registry.find(binding_id) is not None


class TestNewDeploymentRecordCreated:
    def test_new_deployment_record_created(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "workspace-1", "production", "v1", base))
        history_service.record(_record("deployment-2", "workspace-1", "production", "v2", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
            workspace_id="workspace-1",
            deployment_id="deployment-1",
        )
        rollback_service.rollback(request)

        history = history_service.history("workspace-1")

        assert len(history) == 3
        newest = history[-1]
        assert newest.version == "v1"
        assert newest.deployment_id not in ("deployment-1", "deployment-2")


class TestLatestRollback:
    def test_latest_rollback(self):
        rollback_service, history_service, *_ = _build_context()

        assert rollback_service.latest_rollback("workspace-1") is None

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "workspace-1", "production", "v1", base))
        history_service.record(_record("deployment-2", "workspace-1", "production", "v2", base + timedelta(minutes=5)))

        result = rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
                workspace_id="workspace-1",
                deployment_id="deployment-1",
            )
        )

        assert rollback_service.latest_rollback("workspace-1") == result.restored_deployment


class TestDuplicateRollbackPrevention:
    def test_reject_rollback_to_current_deployment(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "workspace-1", "production", "v1", base))
        history_service.record(_record("deployment-2", "workspace-1", "production", "v2", base + timedelta(minutes=5)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
                    workspace_id="workspace-1",
                    deployment_id="deployment-2",
                )
            )

    def test_rollback_target_no_longer_current_after_first_rollback(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "workspace-1", "production", "v1", base))
        history_service.record(_record("deployment-2", "workspace-1", "production", "v2", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
            workspace_id="workspace-1",
            deployment_id="deployment-1",
        )
        first = rollback_service.rollback(request)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
                    workspace_id="workspace-1",
                    deployment_id=first.restored_deployment.deployment_id,
                )
            )


class TestInvalidRollbackRejection:
    def test_reject_none_request(self):
        rollback_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            rollback_service.rollback(None)

    def test_reject_unknown_workspace(self):
        rollback_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
                    workspace_id="workspace-missing",
                    deployment_id="deployment-1",
                )
            )

    def test_reject_unknown_deployment(self):
        rollback_service, history_service, *_ = _build_context()

        history_service.record(_record("deployment-1", "workspace-1", "production", "v1", datetime.now(timezone.utc)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
                    workspace_id="workspace-1",
                    deployment_id="deployment-missing",
                )
            )

    def test_reject_incomplete_deployment_history(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(
            _record("deployment-1", "workspace-1", "production", "v1", base, deployed_resources={"bindings": ("binding-missing",)})
        )
        history_service.record(_record("deployment-2", "workspace-1", "production", "v2", base + timedelta(minutes=5)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
                    workspace_id="workspace-1",
                    deployment_id="deployment-1",
                )
            )

    def test_reject_blank_ids(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
                workspace_id="   ",
                deployment_id="deployment-1",
            )

    def test_reject_none_dependencies(self):
        _, history_service, binding_registry, template_registry, preset_registry, group_registry = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackService(
                None, binding_registry, template_registry, preset_registry, group_registry
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackService(
                history_service, None, template_registry, preset_registry, group_registry
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackService(
                history_service, binding_registry, None, preset_registry, group_registry
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackService(
                history_service, binding_registry, template_registry, None, group_registry
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackService(
                history_service, binding_registry, template_registry, preset_registry, None
            )


class TestImmutableRollbackResult:
    def test_immutable_result(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "workspace-1", "production", "v1", base))
        history_service.record(_record("deployment-2", "workspace-1", "production", "v2", base + timedelta(minutes=5)))

        result = rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest(
                workspace_id="workspace-1",
                deployment_id="deployment-1",
            )
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False
