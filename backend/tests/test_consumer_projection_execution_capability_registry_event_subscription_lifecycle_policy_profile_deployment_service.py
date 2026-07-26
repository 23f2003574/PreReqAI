import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService,
)


def _build_profile(profile_id="development", policy_identifiers=("policy-a",)):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,

        profile_name=profile_id,

        description=f"Profile {profile_id}.",

        policy_identifiers=policy_identifiers,
    )


def _build_version(version_id, policy_identifiers=("policy-a",)):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
        version=version_id,

        policy_identifiers=policy_identifiers,

        created_at=datetime.now(timezone.utc),
    )


def _build_service(profile_id="development", versions=(("1.0.0", ("policy-a",)),)):
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

    validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator()

    compatibility_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityService(
        resolver,

        version_service,
    )

    deployment_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentService(
        resolver,

        version_service,

        validator,

        compatibility_service,
    )

    return deployment_service, registry, version_service


class TestDeployProfile:
    """deploy() publishes a specific requested version into the target environment."""

    def test_deploy_profile(self):
        service, _, _ = _build_service()

        result = service.deploy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                profile_id="development",

                version="1.0.0",

                target_environment="staging",

                parameter_values={
                    "threshold": 5,
                },
            )
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentResult,
        )
        assert result.successful is True
        assert result.target_environment == "staging"
        assert result.deployed_profile.version == "1.0.0"
        assert dict(result.deployed_profile.parameter_values) == {"threshold": 5}
        assert result.deployment_id == "development::staging"


class TestDeployLatestVersion:
    """Omitting a version deploys the profile's current version."""

    def test_deploy_latest_version(self):
        service, _, version_service = _build_service(
            versions=(
                ("1.0.0", ("policy-a",)),

                ("1.1.0", ("policy-a", "policy-b")),
            ),
        )

        result = service.deploy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                profile_id="development",

                version=None,

                target_environment="staging",

                parameter_values=None,
            )
        )

        assert result.deployed_profile.version == version_service.latest("development").version
        assert result.deployed_profile.version == "1.1.0"


class TestDeployReplacement:
    """deploy_or_replace() succeeds and reuses the same deployment ID for an already-deployed environment."""

    def test_deploy_replacement(self):
        service, _, _ = _build_service(
            versions=(
                ("1.0.0", ("policy-a",)),

                ("1.1.0", ("policy-a", "policy-b")),
            ),
        )

        first = service.deploy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                profile_id="development",

                version="1.0.0",

                target_environment="staging",

                parameter_values=None,
            )
        )

        second = service.deploy_or_replace(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                profile_id="development",

                version="1.1.0",

                target_environment="staging",

                parameter_values=None,
            )
        )

        assert second.successful is True
        assert second.deployment_id == first.deployment_id
        assert second.deployed_profile.version == "1.1.0"


class TestCanDeployTrue:
    """can_deploy() reports True for a resolvable, valid, compatible, undeployed profile version."""

    def test_can_deploy_true(self):
        service, _, _ = _build_service()

        assert service.can_deploy(
            "development",

            "1.0.0",

            "staging",
        ) is True

    def test_can_deploy_true_latest(self):
        service, _, _ = _build_service()

        assert service.can_deploy(
            "development",

            None,

            "staging",
        ) is True


class TestCanDeployFalse:
    """can_deploy() reports False without raising for various failure conditions."""

    def test_can_deploy_false_missing_profile(self):
        service, _, _ = _build_service()

        assert service.can_deploy(
            "does-not-exist",

            "1.0.0",

            "staging",
        ) is False

    def test_can_deploy_false_missing_version(self):
        service, _, _ = _build_service()

        assert service.can_deploy(
            "development",

            "9.9.9",

            "staging",
        ) is False

    def test_can_deploy_false_incompatible_version(self):
        service, _, _ = _build_service(
            versions=(
                ("1.0.0", ()),
            ),
        )

        assert service.can_deploy(
            "development",

            "1.0.0",

            "staging",
        ) is False

    def test_can_deploy_false_already_deployed(self):
        service, _, _ = _build_service()

        service.deploy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                profile_id="development",

                version="1.0.0",

                target_environment="staging",

                parameter_values=None,
            )
        )

        assert service.can_deploy(
            "development",

            "1.0.0",

            "staging",
        ) is False


class TestDuplicateDeploymentRejection:
    """deploy() rejects a second deployment to an environment already actively deployed to."""

    def test_duplicate_deployment_rejection(self):
        service, _, _ = _build_service()

        service.deploy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                profile_id="development",

                version="1.0.0",

                target_environment="staging",

                parameter_values=None,
            )
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                    profile_id="development",

                    version="1.0.0",

                    target_environment="staging",

                    parameter_values=None,
                )
            )


class TestImmutableDeploymentResult:
    """A deployment result and its deployed profile cannot be reassigned."""

    def test_immutable_deployment_result(self):
        service, _, _ = _build_service()

        result = service.deploy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                profile_id="development",

                version="1.0.0",

                target_environment="staging",

                parameter_values=None,
            )
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.successful = False

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.deployed_profile.version = "9.9.9"

    def test_does_not_mutate_stored_version(self):
        service, _, version_service = _build_service()

        service.deploy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                profile_id="development",

                version="1.0.0",

                target_environment="staging",

                parameter_values={"threshold": 5},
            )
        )

        assert version_service.find("development", "1.0.0").policy_identifiers == ("policy-a",)


class TestInvalidDeploymentRequestRejection:
    """None inputs, blank identifiers, and nonexistent profiles/versions are rejected."""

    def test_reject_none_request(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError
        ):
            service.deploy(None)

    def test_reject_wrong_request_type(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError
        ):
            service.deploy("not-a-request")

    def test_reject_blank_profile_id(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                    profile_id="   ",

                    version="1.0.0",

                    target_environment="staging",

                    parameter_values=None,
                )
            )

    def test_reject_blank_target_environment(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                    profile_id="development",

                    version="1.0.0",

                    target_environment="   ",

                    parameter_values=None,
                )
            )

    def test_reject_blank_version(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                    profile_id="development",

                    version="   ",

                    target_environment="staging",

                    parameter_values=None,
                )
            )

    def test_reject_nonexistent_profile(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                    profile_id="does-not-exist",

                    version="1.0.0",

                    target_environment="staging",

                    parameter_values=None,
                )
            )

    def test_reject_nonexistent_version(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                    profile_id="development",

                    version="9.9.9",

                    target_environment="staging",

                    parameter_values=None,
                )
            )

    def test_reject_incompatible_deployment(self):
        service, _, _ = _build_service(
            versions=(
                ("1.0.0", ()),
            ),
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                    profile_id="development",

                    version="1.0.0",

                    target_environment="staging",

                    parameter_values=None,
                )
            )

    def test_reject_invalid_parameter_values(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest(
                    profile_id="development",

                    version="1.0.0",

                    target_environment="staging",

                    parameter_values="not-a-mapping",
                )
            )
