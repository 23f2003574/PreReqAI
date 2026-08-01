import dataclasses

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
)


class FakeClock:
    def __init__(self, now):
        self.current = now

    def now(self):
        return self.current


def _binding(binding_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id="development",
        capability_id=f"capability-{binding_id}",
        created_at=datetime.now(timezone.utc),
    )


def _template(template_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=binding_ids,
        metadata={},
    )


def _preset(preset_id, binding_template_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPreset(
        preset_id=preset_id,
        name=preset_id,
        description="A preset.",
        binding_template_ids=binding_template_ids,
    )


def _record(deployment_id, preset_id, environment, version, deployed_at, instantiated_binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRecord(
        deployment_id=deployment_id,
        preset_id=preset_id,
        environment=environment,
        version=version,
        instantiated_binding_ids=instantiated_binding_ids,
        deployed_at=deployed_at,
        status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentStatus.SUCCEEDED,
    )


def _build_context():
    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    binding_registry.register(_binding("binding-1"))
    binding_registry.register(_binding("binding-2"))
    binding_registry.register(_binding("binding-3"))

    activation_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingActivationService(
        binding_registry,
        FakeClock(datetime.now(timezone.utc)),
    )

    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    template_registry.register(_template("template-1", binding_ids=("binding-1",)))
    template_registry.register(_template("template-2", binding_ids=("binding-2", "binding-3")))

    preset_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    preset_registry.register(_preset("preset-1", binding_template_ids=("template-1", "template-2")))

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetParameterizationService(
        preset_registry,
        {},
    )

    preset_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionService(
        preset_registry,
        parameterization_service,
    )
    preset_version_service.publish("preset-1", "1.0.0")

    preset_registry.replace(_preset("preset-1", binding_template_ids=("template-1",)))
    preset_version_service.publish("preset-1", "2.0.0")

    history_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentHistoryService()

    rollback_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackService(
        history_service,
        preset_version_service,
        template_registry,
        binding_registry,
        activation_service,
    )

    return rollback_service, history_service, preset_version_service, template_registry, preset_registry, binding_registry, activation_service


class TestSuccessfulRollback:
    def test_successful_rollback(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "preset-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "preset-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
            preset_id="preset-1",
            deployment_id="deployment-1",
        )

        result = rollback_service.rollback(request)

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackResult)
        assert result.successful is True
        assert result.previous_deployment.deployment_id == "deployment-2"
        assert result.restored_deployment.version == "1.0.0"
        assert result.restored_deployment.environment == "production"


class TestRollbackEligibility:
    def test_rollback_eligibility(self):
        rollback_service, history_service, *_ = _build_context()

        assert rollback_service.can_rollback("preset-1") is False

        history_service.record(_record("deployment-1", "preset-1", "production", "1.0.0", datetime.now(timezone.utc)))
        assert rollback_service.can_rollback("preset-1") is False

        history_service.record(_record("deployment-2", "preset-1", "production", "2.0.0", datetime.now(timezone.utc)))
        assert rollback_service.can_rollback("preset-1") is True

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            rollback_service.can_rollback("   ")


class TestRollbackHistory:
    def test_rollback_history(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "preset-1", "production", "1.0.0", base)
        second = _record("deployment-2", "preset-1", "production", "2.0.0", base + timedelta(minutes=5))

        history_service.record(first)
        history_service.record(second)

        assert rollback_service.rollback_history("preset-1") == (first, second)


class TestRecreatedBindingsMatchTargetDeployment:
    def test_recreated_bindings_match_target_deployment(self):
        rollback_service, history_service, _, _, _, binding_registry, activation_service = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "preset-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "preset-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
            preset_id="preset-1",
            deployment_id="deployment-1",
        )

        result = rollback_service.rollback(request)

        assert len(result.instantiated_binding_ids) == 3
        assert result.instantiated_binding_ids == result.restored_deployment.instantiated_binding_ids

        for recreated_id in result.instantiated_binding_ids:
            recreated = binding_registry.find(recreated_id)

            assert recreated is not None
            assert recreated.profile_id == "development"
            assert activation_service.state(recreated_id) is not None
            assert recreated_id not in ("binding-1", "binding-2", "binding-3")


class TestNewDeploymentRecordCreated:
    def test_new_deployment_record_created(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "preset-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "preset-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
            preset_id="preset-1",
            deployment_id="deployment-1",
        )
        rollback_service.rollback(request)

        history = history_service.history("preset-1")

        assert len(history) == 3
        newest = history[-1]
        assert newest.version == "1.0.0"
        assert newest.deployment_id not in ("deployment-1", "deployment-2")


class TestLatestRollback:
    def test_latest_rollback(self):
        rollback_service, history_service, *_ = _build_context()

        assert rollback_service.latest_rollback("preset-1") is None

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "preset-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "preset-1", "production", "2.0.0", base + timedelta(minutes=5)))

        result = rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
                preset_id="preset-1",
                deployment_id="deployment-1",
            )
        )

        assert rollback_service.latest_rollback("preset-1") == result.restored_deployment


class TestDuplicateRollbackPrevention:
    def test_reject_rollback_to_current_deployment(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "preset-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "preset-1", "production", "2.0.0", base + timedelta(minutes=5)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
                    preset_id="preset-1",
                    deployment_id="deployment-2",
                )
            )

    def test_rollback_target_no_longer_current_after_first_rollback(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "preset-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "preset-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
            preset_id="preset-1",
            deployment_id="deployment-1",
        )
        first = rollback_service.rollback(request)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
                    preset_id="preset-1",
                    deployment_id=first.restored_deployment.deployment_id,
                )
            )


class TestInvalidRollbackRejection:
    def test_reject_none_request(self):
        rollback_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            rollback_service.rollback(None)

    def test_reject_unknown_preset(self):
        rollback_service, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
                    preset_id="preset-missing",
                    deployment_id="deployment-1",
                )
            )

    def test_reject_unknown_deployment(self):
        rollback_service, history_service, *_ = _build_context()

        history_service.record(_record("deployment-1", "preset-1", "production", "1.0.0", datetime.now(timezone.utc)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
                    preset_id="preset-1",
                    deployment_id="deployment-missing",
                )
            )

    def test_reject_incomplete_deployment_history(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "preset-1", "production", "version-never-published", base))
        history_service.record(_record("deployment-2", "preset-1", "production", "2.0.0", base + timedelta(minutes=5)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
                    preset_id="preset-1",
                    deployment_id="deployment-1",
                )
            )

    def test_reject_blank_ids(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
                preset_id="   ",
                deployment_id="deployment-1",
            )

    def test_reject_none_dependencies(self):
        _, history_service, preset_version_service, template_registry, _, binding_registry, activation_service = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackService(
                None, preset_version_service, template_registry, binding_registry, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackService(
                history_service, None, template_registry, binding_registry, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackService(
                history_service, preset_version_service, None, binding_registry, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackService(
                history_service, preset_version_service, template_registry, None, activation_service
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackService(
                history_service, preset_version_service, template_registry, binding_registry, None
            )


class TestImmutableRollbackResult:
    def test_immutable_result(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "preset-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "preset-1", "production", "2.0.0", base + timedelta(minutes=5)))

        result = rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest(
                preset_id="preset-1",
                deployment_id="deployment-1",
            )
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False
