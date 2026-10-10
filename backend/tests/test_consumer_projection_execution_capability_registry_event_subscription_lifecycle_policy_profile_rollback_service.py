import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService,
)


def _build_profile(profile_id="development", policy_identifiers=("policy-a", "policy-b")):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,

        profile_name=profile_id,

        description=f"Profile {profile_id}.",

        policy_identifiers=policy_identifiers,
    )


def _build_version(version_id, policy_identifiers):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
        version=version_id,

        policy_identifiers=policy_identifiers,

        created_at=datetime.now(timezone.utc),
    )


def _build_deployment_record(deployment_id, profile_id, version, target_environment):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRecord(
        deployment_id=deployment_id,

        profile_id=profile_id,

        version=version,

        target_environment=target_environment,

        deployed_at=datetime.now(timezone.utc),

        deployment_status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentStatus.SUCCEEDED,
    )


def _build_service(profile_id="development", versions=(("1.0.0", ("policy-a",)), ("1.1.0", ("policy-a", "policy-b")))):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
    registry.register(
        _build_profile(
            profile_id
        )
    )

    version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

    for version_id, policy_identifiers in versions:

        version_service.publish(

            profile_id,

            _build_version(

                version_id,

                policy_identifiers,
            ),
        )

    resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
        registry
    )

    compatibility_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService(
        resolver,

        version_service,
    )

    deployment_history_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()

    rollback_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackService(
        deployment_history_service,

        compatibility_service,
    )

    return rollback_service, deployment_history_service, version_service


def _seed_deployment_trail(deployment_history_service, profile_id, target_environment):

    deployment_history_service.record(
        _build_deployment_record(
            "deployment-1",

            profile_id,

            "1.0.0",

            target_environment,
        )
    )

    deployment_history_service.record(
        _build_deployment_record(
            "deployment-2",

            profile_id,

            "1.1.0",

            target_environment,
        )
    )


class TestSuccessfulRollback:
    """rollback() restores a previously deployed version and records a new deployment."""

    def test_successful_rollback(self):
        service, deployment_history_service, _ = _build_service()
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        result = service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest(
                profile_id="development",

                target_environment="staging",

                target_version="1.0.0",

                reason="Regression detected in 1.1.0.",
            )
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackResult,
        )
        assert result.successful is True
        assert result.previous_version == "1.1.0"
        assert result.restored_version == "1.0.0"


class TestRollbackEligibility:
    """can_rollback() reports whether a rollback would currently succeed."""

    def test_rollback_eligibility_true(self):
        service, deployment_history_service, _ = _build_service()
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        assert service.can_rollback(
            "development",

            "staging",

            "1.0.0",
        ) is True

    def test_rollback_eligibility_false_never_deployed_environment(self):
        service, deployment_history_service, _ = _build_service()

        assert service.can_rollback(
            "development",

            "staging",

            "1.0.0",
        ) is False

    def test_rollback_eligibility_false_never_deployed_version(self):
        service, deployment_history_service, _ = _build_service(
            versions=(
                ("1.0.0", ("policy-a",)),

                ("1.1.0", ("policy-a", "policy-b")),

                ("2.0.0", ("policy-a",)),
            ),
        )
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        assert service.can_rollback(
            "development",

            "staging",

            "2.0.0",
        ) is False


class TestRollbackHistoryRetrieval:
    """rollback_history() returns every deployment recorded for a profile."""

    def test_rollback_history_retrieval(self):
        service, deployment_history_service, _ = _build_service()
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        history = service.rollback_history(
            "development"
        )

        assert [
            record.deployment_id
            for record
            in history
        ] == ["deployment-1", "deployment-2"]


class TestRejectRollbackWithoutDeploymentHistory:
    """Rolling back a profile and environment with no deployment history is rejected."""

    def test_reject_rollback_without_deployment_history(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError
        ):
            service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest(
                    profile_id="development",

                    target_environment="staging",

                    target_version="1.0.0",

                    reason="No prior deployment exists.",
                )
            )


class TestRejectRollbackToActiveVersion:
    """Rolling back to the version that is already active is rejected."""

    def test_reject_rollback_to_active_version(self):
        service, deployment_history_service, _ = _build_service()
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError
        ):
            service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest(
                    profile_id="development",

                    target_environment="staging",

                    target_version="1.1.0",

                    reason="Attempting a no-op rollback.",
                )
            )


class TestCompatibilityValidationDuringRollback:
    """Rolling back to an incompatible version is rejected."""

    def test_compatibility_validation_during_rollback(self):
        service, deployment_history_service, _ = _build_service(
            versions=(
                ("1.0.0", ()),

                ("1.1.0", ("policy-a",)),
            ),
        )
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError
        ):
            service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest(
                    profile_id="development",

                    target_environment="staging",

                    target_version="1.0.0",

                    reason="Rolling back to an incompatible version.",
                )
            )

        assert service.can_rollback(
            "development",

            "staging",

            "1.0.0",
        ) is False


class TestImmutableRollbackResult:
    """A rollback result cannot have its fields reassigned."""

    def test_immutable_rollback_result(self):
        service, deployment_history_service, _ = _build_service()
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        result = service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest(
                profile_id="development",

                target_environment="staging",

                target_version="1.0.0",

                reason="Regression detected in 1.1.0.",
            )
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False


class TestDeploymentHistoryPreservedAfterRollback:
    """Rolling back appends a new record without modifying or removing prior ones."""

    def test_deployment_history_preserved_after_rollback(self):
        service, deployment_history_service, _ = _build_service()
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        service.rollback(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest(
                profile_id="development",

                target_environment="staging",

                target_version="1.0.0",

                reason="Regression detected in 1.1.0.",
            )
        )

        history = deployment_history_service.history(
            "development"
        )

        assert len(history) == 3
        assert history[0].deployment_id == "deployment-1"
        assert history[0].version == "1.0.0"
        assert history[1].deployment_id == "deployment-2"
        assert history[1].version == "1.1.0"
        assert history[2].version == "1.0.0"
        assert history[2].deployment_id not in {"deployment-1", "deployment-2"}


class TestRejectInvalidInputs:
    """None requests and blank identifiers are rejected."""

    def test_reject_none_request(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError
        ):
            service.rollback(None)

    def test_reject_blank_profile_id(self):
        service, deployment_history_service, _ = _build_service()
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError
        ):
            service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest(
                    profile_id="   ",

                    target_environment="staging",

                    target_version="1.0.0",

                    reason="Testing blank profile ID.",
                )
            )

    def test_reject_blank_target_environment(self):
        service, deployment_history_service, _ = _build_service()
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError
        ):
            service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest(
                    profile_id="development",

                    target_environment="   ",

                    target_version="1.0.0",

                    reason="Testing blank target environment.",
                )
            )

    def test_reject_blank_target_version(self):
        service, deployment_history_service, _ = _build_service()
        _seed_deployment_trail(deployment_history_service, "development", "staging")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError
        ):
            service.rollback(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest(
                    profile_id="development",

                    target_environment="staging",

                    target_version="   ",

                    reason="Testing blank target version.",
                )
            )
