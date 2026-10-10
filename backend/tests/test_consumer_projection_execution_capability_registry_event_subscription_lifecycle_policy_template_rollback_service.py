import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService,
)


_STATE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (_STATE.REGISTERED, _STATE.ACTIVE),

        initial_state,
    )


def _build_version(version_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion(
        version=version_id,

        lifecycle_policy=_build_policy(
            _STATE.REGISTERED,
        ),

        created_at=datetime.now(timezone.utc),
    )


def _build_deployment(deployment_id, template_id="standard-registration", target_registry="production"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord(
        deployment_id=deployment_id,

        template_id=template_id,

        template_version="1.0.0",

        target_registry=target_registry,

        deployed_at=datetime.now(timezone.utc),
    )


def _build_environment(*version_ids, template_id="standard-registration"):
    version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()

    for version_id in version_ids:

        version_service.publish(
            template_id,

            _build_version(
                version_id
            ),
        )

    deployment_history_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()
    deployment_history_service.record(
        _build_deployment(
            "deployment-1",

            template_id=template_id,
        )
    )

    rollback_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackService(
        deployment_history_service,

        version_service,
    )

    return (

        rollback_service,

        deployment_history_service,

        version_service,
    )


class TestSuccessfulRollback:
    """Rolling back to an earlier published version succeeds."""

    def test_successful_rollback(self):
        rollback_service, deployment_history_service, version_service = _build_environment(
            "1.0.0",

            "1.1.0",

            "2.0.0",
        )

        result = rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest(
                deployment_id="deployment-1",

                target_version="1.1.0",
            )
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackResult,
        )
        assert result.rollback_successful is True
        assert result.previous_version == "2.0.0"
        assert result.restored_version == "1.1.0"
        assert version_service.latest("standard-registration").version == "1.1.0"


class TestRollbackToEarliestVersion:
    """Rolling back all the way to the first published version succeeds."""

    def test_rollback_to_earliest_version(self):
        rollback_service, deployment_history_service, version_service = _build_environment(
            "1.0.0",

            "1.1.0",

            "2.0.0",
        )

        result = rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest(
                deployment_id="deployment-1",

                target_version="1.0.0",
            )
        )

        assert result.restored_version == "1.0.0"
        assert version_service.latest("standard-registration").version == "1.0.0"
        assert len(
            version_service.history("standard-registration").versions
        ) == 3


class TestCanRollback:
    """can_rollback() reports whether an earlier version exists."""

    def test_can_rollback_true(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        assert rollback_service.can_rollback("deployment-1") is True

    def test_can_rollback_false_single_version(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",
        )

        assert rollback_service.can_rollback("deployment-1") is False

    def test_can_rollback_false_missing_deployment(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        assert rollback_service.can_rollback("does-not-exist") is False


class TestRollbackHistory:
    """rollback_history() lists every deployment recorded for the template."""

    def test_rollback_history(self):
        rollback_service, deployment_history_service, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest(
                deployment_id="deployment-1",

                target_version="1.0.0",
            )
        )

        history = rollback_service.rollback_history(
            "deployment-1"
        )

        assert len(history) == 2
        assert history[0].deployment_id == "deployment-1"
        assert history[1].template_version == "1.0.0"
        assert history == deployment_history_service.history("standard-registration")


class TestMissingDeployment:
    """Rolling back an unknown deployment ID is rejected."""

    def test_missing_deployment(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError
        ):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest(
                    deployment_id="does-not-exist",

                    target_version="1.0.0",
                )
            )

    def test_missing_deployment_for_rollback_history(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError
        ):
            rollback_service.rollback_history(
                "does-not-exist"
            )


class TestMissingVersion:
    """Rolling back to a never-published version is rejected."""

    def test_missing_version(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError
        ):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest(
                    deployment_id="deployment-1",

                    target_version="9.9.9",
                )
            )

    def test_reject_rollback_to_current_version(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError
        ):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest(
                    deployment_id="deployment-1",

                    target_version="1.1.0",
                )
            )


class TestImmutableDeploymentHistory:
    """A rollback records a new deployment without disturbing prior ones."""

    def test_immutable_deployment_history(self):
        rollback_service, deployment_history_service, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        original_record = deployment_history_service.find(
            "deployment-1"
        )
        snapshot = deployment_history_service.list()

        rollback_service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest(
                deployment_id="deployment-1",

                target_version="1.0.0",
            )
        )

        assert deployment_history_service.find("deployment-1") is original_record
        assert len(snapshot) == 1
        assert len(deployment_history_service.list()) == 2

        with pytest.raises(dataclasses.FrozenInstanceError):
            original_record.template_version = "changed"


class TestRejectInvalidInputs:
    """None requests and blank identifiers are rejected."""

    def test_reject_none_request(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError
        ):
            rollback_service.rollback(
                None
            )

    def test_reject_blank_deployment_id(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError
        ):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest(
                    deployment_id="   ",

                    target_version="1.0.0",
                )
            )

    def test_reject_blank_target_version(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError
        ):
            rollback_service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest(
                    deployment_id="deployment-1",

                    target_version="   ",
                )
            )

    def test_reject_blank_can_rollback_identifier(self):
        rollback_service, _, _ = _build_environment(
            "1.0.0",

            "1.1.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError
        ):
            rollback_service.can_rollback("   ")
