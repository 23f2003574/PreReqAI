import dataclasses

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionService,
)


def _group(group_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
        group_id=group_id,
        group_name=group_id,
        binding_ids=binding_ids,
    )


def _record(deployment_id, group_id, environment, version, deployed_at):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRecord(
        deployment_id=deployment_id,
        group_id=group_id,
        environment=environment,
        version=version,
        deployed_at=deployed_at,
        status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentStatus.SUCCEEDED,
    )


def _build_context():
    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()
    group_registry.register(_group("group-1", binding_ids=("binding-1",)))

    group_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionService(
        group_registry
    )
    group_version_service.publish("group-1", "1.0.0")

    group_registry.replace(_group("group-1", binding_ids=("binding-1", "binding-2")))
    group_version_service.publish("group-1", "2.0.0")

    history_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentHistoryService()

    rollback_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackService(
        history_service, group_version_service
    )

    return rollback_service, history_service, group_version_service, group_registry


class TestSuccessfulRollback:
    def test_successful_rollback(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "group-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "group-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
            group_id="group-1",
            deployment_id="deployment-1",
        )

        result = rollback_service.rollback(request)

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackResult)
        assert result.successful is True
        assert result.previous_deployment.deployment_id == "deployment-2"
        assert result.restored_deployment.version == "1.0.0"
        assert result.restored_deployment.environment == "production"


class TestRollbackEligibility:
    def test_rollback_eligibility(self):
        rollback_service, history_service, *_ = _build_context()

        assert rollback_service.can_rollback("group-1") is False

        history_service.record(_record("deployment-1", "group-1", "production", "1.0.0", datetime.now(timezone.utc)))
        assert rollback_service.can_rollback("group-1") is False

        history_service.record(_record("deployment-2", "group-1", "production", "2.0.0", datetime.now(timezone.utc)))
        assert rollback_service.can_rollback("group-1") is True

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError):
            rollback_service.can_rollback("   ")


class TestAtomicRestoration:
    def test_restored_bindings_are_atomic(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "group-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "group-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
            group_id="group-1",
            deployment_id="deployment-1",
        )

        result = rollback_service.rollback(request)

        assert result.restored_bindings == ("binding-1",)


class TestRollbackHistory:
    def test_rollback_history(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        first = _record("deployment-1", "group-1", "production", "1.0.0", base)
        second = _record("deployment-2", "group-1", "production", "2.0.0", base + timedelta(minutes=5))

        history_service.record(first)
        history_service.record(second)

        assert rollback_service.rollback_history("group-1") == (first, second)


class TestNewDeploymentRecordCreated:
    def test_new_deployment_record_created(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "group-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "group-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
            group_id="group-1",
            deployment_id="deployment-1",
        )
        rollback_service.rollback(request)

        history = history_service.history("group-1")

        assert len(history) == 3
        newest = history[-1]
        assert newest.version == "1.0.0"
        assert newest.deployment_id not in ("deployment-1", "deployment-2")


class TestCurrentDeploymentUpdated:
    def test_current_deployment_updated_after_rollback(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "group-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "group-1", "production", "2.0.0", base + timedelta(minutes=5)))

        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
            group_id="group-1",
            deployment_id="deployment-1",
        )
        result = rollback_service.rollback(request)

        assert history_service.latest("group-1") == result.restored_deployment
        assert history_service.latest("group-1").version == "1.0.0"


class TestLatestRollback:
    def test_latest_rollback(self):
        rollback_service, history_service, *_ = _build_context()

        assert rollback_service.latest_rollback("group-1") is None

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "group-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "group-1", "production", "2.0.0", base + timedelta(minutes=5)))

        result = rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
                group_id="group-1",
                deployment_id="deployment-1",
            )
        )

        assert rollback_service.latest_rollback("group-1") == result.restored_deployment


class TestInvalidRollbackRejection:
    def test_reject_none_request(self):
        rollback_service, _, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError):
            rollback_service.rollback(None)

    def test_reject_unknown_group(self):
        rollback_service, _, *_ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
                    group_id="group-missing",
                    deployment_id="deployment-1",
                )
            )

    def test_reject_unknown_deployment(self):
        rollback_service, history_service, *_ = _build_context()

        history_service.record(_record("deployment-1", "group-1", "production", "1.0.0", datetime.now(timezone.utc)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
                    group_id="group-1",
                    deployment_id="deployment-missing",
                )
            )

    def test_reject_rollback_to_current_deployment(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "group-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "group-1", "production", "2.0.0", base + timedelta(minutes=5)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
                    group_id="group-1",
                    deployment_id="deployment-2",
                )
            )

    def test_reject_incomplete_deployment_history(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "group-1", "production", "version-never-published", base))
        history_service.record(_record("deployment-2", "group-1", "production", "2.0.0", base + timedelta(minutes=5)))

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
                    group_id="group-1",
                    deployment_id="deployment-1",
                )
            )

    def test_reject_blank_ids(self):
        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
                group_id="   ",
                deployment_id="deployment-1",
            )

    def test_reject_none_dependencies(self):
        _, history_service, group_version_service, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackService(None, group_version_service)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackService(history_service, None)


class TestImmutableRollbackResult:
    def test_immutable_result(self):
        rollback_service, history_service, *_ = _build_context()

        base = datetime.now(timezone.utc)
        history_service.record(_record("deployment-1", "group-1", "production", "1.0.0", base))
        history_service.record(_record("deployment-2", "group-1", "production", "2.0.0", base + timedelta(minutes=5)))

        result = rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest(
                group_id="group-1",
                deployment_id="deployment-1",
            )
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False
