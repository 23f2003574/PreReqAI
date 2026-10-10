import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRelease,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver,
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


def _build_service(profile_id="development", versions=("1.0.0", "1.1.0")):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
    registry.register(
        _build_profile(
            profile_id
        )
    )

    version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

    for version_id in versions:

        version_service.publish(

            profile_id,

            _build_version(
                version_id
            ),
        )

    resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(
        registry
    )

    release_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseService(
        resolver,

        version_service,
    )

    return release_service, registry, version_service


def _is_eligible_for_deployment(release_service, profile_id, version):

    return release_service.is_released(

        profile_id,

        version,
    )


class TestReleaseProfileVersion:
    """release() promotes a version from DRAFT to RELEASED."""

    def test_release_profile_version(self):
        service, _, _ = _build_service()

        result = service.release(
            "development",

            "1.0.0",
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseResult,
        )
        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.DRAFT
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RELEASED
        assert isinstance(
            result.release,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRelease,
        )
        assert result.release.profile_id == "development"
        assert result.release.version == "1.0.0"
        assert result.release.released_at is not None


class TestRetireReleasedVersion:
    """retire() demotes a version from RELEASED to RETIRED, preserving released_at."""

    def test_retire_released_version(self):
        service, _, _ = _build_service()
        released = service.release(
            "development",

            "1.0.0",
        )

        result = service.retire(
            "development",

            "1.0.0",
        )

        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RELEASED
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RETIRED
        assert result.release.released_at == released.release.released_at


class TestLatestReleaseLookup:
    """latest_release() returns the currently released version, not just the most recent release() call."""

    def test_latest_release_lookup(self):
        service, _, _ = _build_service()
        service.release(
            "development",

            "1.0.0",
        )
        service.release(
            "development",

            "1.1.0",
        )

        latest = service.latest_release(
            "development"
        )

        assert latest.version == "1.1.0"

    def test_latest_release_none(self):
        service, _, _ = _build_service()

        assert service.latest_release(
            "development"
        ) is None

    def test_latest_release_ignores_retired(self):
        service, _, _ = _build_service()
        service.release(
            "development",

            "1.0.0",
        )
        service.retire(
            "development",

            "1.0.0",
        )

        assert service.latest_release(
            "development"
        ) is None


class TestIsReleasedTrue:
    """is_released() reports True for a version currently holding RELEASED status."""

    def test_is_released_true(self):
        service, _, _ = _build_service()
        service.release(
            "development",

            "1.0.0",
        )

        assert service.is_released(
            "development",

            "1.0.0",
        ) is True


class TestIsReleasedFalse:
    """is_released() reports False for a version that was never released, or was retired."""

    def test_is_released_false_never_released(self):
        service, _, _ = _build_service()

        assert service.is_released(
            "development",

            "1.0.0",
        ) is False

    def test_is_released_false_retired(self):
        service, _, _ = _build_service()
        service.release(
            "development",

            "1.0.0",
        )
        service.retire(
            "development",

            "1.0.0",
        )

        assert service.is_released(
            "development",

            "1.0.0",
        ) is False


class TestRejectDuplicateRelease:
    """Releasing a version that is already released is rejected."""

    def test_reject_duplicate_release(self):
        service, _, _ = _build_service()
        service.release(
            "development",

            "1.0.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError
        ):
            service.release(
                "development",

                "1.0.0",
            )


class TestRejectInvalidStatusTransition:
    """Retiring a never-released or already-retired version is rejected."""

    def test_reject_retiring_never_released_version(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError
        ):
            service.retire(
                "development",

                "1.0.0",
            )

    def test_reject_retiring_already_retired_version(self):
        service, _, _ = _build_service()
        service.release(
            "development",

            "1.0.0",
        )
        service.retire(
            "development",

            "1.0.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError
        ):
            service.retire(
                "development",

                "1.0.0",
            )

    def test_reject_releasing_retired_version(self):
        service, _, _ = _build_service()
        service.release(
            "development",

            "1.0.0",
        )
        service.retire(
            "development",

            "1.0.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError
        ):
            service.release(
                "development",

                "1.0.0",
            )


class TestImmutableReleaseHistory:
    """A release result and its release record cannot be reassigned, and prior records are untouched."""

    def test_immutable_release_history(self):
        service, _, _ = _build_service()

        released = service.release(
            "development",

            "1.0.0",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            released.current_status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RETIRED

        with pytest.raises(dataclasses.FrozenInstanceError):
            released.release.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RETIRED

        service.retire(
            "development",

            "1.0.0",
        )

        assert released.release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseStatus.RELEASED


class TestDeploymentAllowedOnlyForReleasedVersions:
    """A version is only eligible for deployment while it holds RELEASED status."""

    def test_deployment_allowed_only_for_released_versions(self):
        service, _, _ = _build_service()

        assert _is_eligible_for_deployment(service, "development", "1.0.0") is False

        service.release(
            "development",

            "1.0.0",
        )

        assert _is_eligible_for_deployment(service, "development", "1.0.0") is True

        service.retire(
            "development",

            "1.0.0",
        )

        assert _is_eligible_for_deployment(service, "development", "1.0.0") is False


class TestRejectInvalidInputs:
    """None inputs, blank identifiers, and nonexistent profiles/versions are rejected."""

    def test_reject_blank_profile_id(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError
        ):
            service.release("   ", "1.0.0")

    def test_reject_blank_version(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError
        ):
            service.release("development", "   ")

    def test_reject_nonexistent_profile(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError
        ):
            service.release("does-not-exist", "1.0.0")

    def test_reject_nonexistent_version(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseError
        ):
            service.release("development", "9.9.9")
