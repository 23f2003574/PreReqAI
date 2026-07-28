import dataclasses

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackService,
)


def _record(
    deployment_id,
    binding_id,
    environment,
    version,
    deployed_at,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord(
        deployment_id=deployment_id,
        binding_id=binding_id,
        environment=environment,
        version=version,
        deployed_at=deployed_at,
        status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentStatus.SUCCEEDED,
    )


def _build_context():
    history_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService()
    rollback_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackService(history_service)

    return rollback_service, history_service


class TestSuccessfulRollback:
    def test_successful_rollback(self):
        rollback_service, history_service = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "binding-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "binding-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest(
            binding_id="binding-1",
            deployment_id="deployment-1",
        )

        result = rollback_service.rollback(request)

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackResult)
        assert result.successful is True
        assert result.previous_deployment.deployment_id == "deployment-2"
        assert result.restored_deployment.version == "1.0.0"
        assert result.restored_deployment.environment == "production"


class TestRollbackEligibility:
    def test_rollback_eligibility(self):
        rollback_service, history_service = _build_context()

        assert rollback_service.can_rollback("binding-1") is False

        history_service.record(_record("deployment-1", "binding-1", "production", "1.0.0", datetime.now(timezone.utc)))
        assert rollback_service.can_rollback("binding-1") is False

        history_service.record(_record("deployment-2", "binding-1", "production", "2.0.0", datetime.now(timezone.utc)))
        assert rollback_service.can_rollback("binding-1") is True

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError):
            rollback_service.can_rollback("   ")


class TestRollbackHistory:
    def test_rollback_history(self):
        rollback_service, history_service = _build_context()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "binding-1", "production", "1.0.0", base)
        second = _record("deployment-2", "binding-1", "production", "2.0.0", base + timedelta(minutes=5))

        history_service.record(first)
        history_service.record(second)

        assert rollback_service.rollback_history("binding-1") == (first, second)


class TestNewDeploymentRecordCreated:
    def test_new_deployment_record_created(self):
        rollback_service, history_service = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "binding-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "binding-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest(
            binding_id="binding-1",
            deployment_id="deployment-1",
        )
        rollback_service.rollback(request)

        history = history_service.history("binding-1")

        assert len(history) == 3
        newest = history[-1]
        assert newest.version == "1.0.0"
        assert newest.deployment_id not in ("deployment-1", "deployment-2")


class TestCurrentDeploymentUpdated:
    def test_current_deployment_updated_after_rollback(self):
        rollback_service, history_service = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "binding-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "binding-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest(
            binding_id="binding-1",
            deployment_id="deployment-1",
        )
        result = rollback_service.rollback(request)

        assert history_service.latest("binding-1") == result.restored_deployment
        assert history_service.latest("binding-1").version == "1.0.0"


class TestInvalidRollbackRejection:
    def test_reject_none_request(self):
        rollback_service, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError):
            rollback_service.rollback(None)

    def test_reject_unknown_binding(self):
        rollback_service, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest(
                    binding_id="binding-missing",
                    deployment_id="deployment-1",
                )
            )

    def test_reject_unknown_deployment(self):
        rollback_service, history_service = _build_context()

        history_service.record(_record("deployment-1", "binding-1", "production", "1.0.0", datetime.now(timezone.utc)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest(
                    binding_id="binding-1",
                    deployment_id="deployment-missing",
                )
            )

    def test_reject_rollback_to_current_deployment(self):
        rollback_service, history_service = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "binding-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "binding-1", "production", "2.0.0", base + timedelta(minutes=5)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest(
                    binding_id="binding-1",
                    deployment_id="deployment-2",
                )
            )

    def test_reject_blank_ids(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest(
                binding_id="   ",
                deployment_id="deployment-1",
            )


class TestImmutableRollbackResult:
    def test_immutable_result(self):
        rollback_service, history_service = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "binding-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "binding-1", "production", "2.0.0", base + timedelta(minutes=5)))

        result = rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest(
                binding_id="binding-1",
                deployment_id="deployment-1",
            )
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False
