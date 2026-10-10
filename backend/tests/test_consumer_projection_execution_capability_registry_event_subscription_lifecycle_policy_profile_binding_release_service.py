import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRelease,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService,
)


def _build_profile(profile_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,
        profile_name=profile_id,
        description=f"Profile {profile_id}.",
        policy_identifiers=(f"policy-{profile_id}",),
    )


def _build_context(profile_id="profile-a"):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
    profile_service.register(_build_profile(profile_id))

    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingService(profile_service)
    binding = binding_service.bind(profile_id, "capability-a")

    version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

    release_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseService(
        binding_service,
        version_service,
    )

    return {
        "release_service": release_service,
        "binding_service": binding_service,
        "version_service": version_service,
        "profile_id": profile_id,
        "binding_id": binding.binding_id,
    }


def _publish(context, version):
    context["version_service"].publish(
        context["profile_id"],
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
            version=version,
            policy_identifiers=(f"policy-{version}",),
            created_at=datetime.now(timezone.utc),
        ),
    )


class TestReleaseVersion:
    def test_release_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        result = context["release_service"].release(context["binding_id"], "1.0.0")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseResult)
        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.DRAFT
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RELEASED
        assert isinstance(result.release, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRelease)
        assert result.release.binding_id == context["binding_id"]
        assert result.release.version == "1.0.0"


class TestRetireVersion:
    def test_retire_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["binding_id"], "1.0.0")
        result = context["release_service"].retire(context["binding_id"], "1.0.0")

        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RELEASED
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RETIRED
        assert context["release_service"].is_released(context["binding_id"], "1.0.0") is False


class TestLatestReleaseLookup:
    def test_latest_release_lookup(self):
        context = _build_context()
        _publish(context, "1.0.0")
        _publish(context, "2.0.0")

        assert context["release_service"].latest_release(context["binding_id"]) is None

        context["release_service"].release(context["binding_id"], "1.0.0")
        latest = context["release_service"].release(context["binding_id"], "2.0.0")

        assert context["release_service"].latest_release(context["binding_id"]) == latest.release

        context["release_service"].retire(context["binding_id"], "2.0.0")

        assert context["release_service"].latest_release(context["binding_id"]).version == "1.0.0"


class TestIsReleasedTrueFalse:
    def test_is_released_true_and_false(self):
        context = _build_context()
        _publish(context, "1.0.0")

        assert context["release_service"].is_released(context["binding_id"], "1.0.0") is False

        context["release_service"].release(context["binding_id"], "1.0.0")

        assert context["release_service"].is_released(context["binding_id"], "1.0.0") is True


class TestDuplicateReleaseRejection:
    def test_reject_duplicate_release(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["binding_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError):
            context["release_service"].release(context["binding_id"], "1.0.0")


class TestInvalidTransitionRejection:
    def test_reject_retiring_non_released_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError):
            context["release_service"].retire(context["binding_id"], "1.0.0")

    def test_reject_re_releasing_retired_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["binding_id"], "1.0.0")
        context["release_service"].retire(context["binding_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError):
            context["release_service"].release(context["binding_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError):
            context["release_service"].retire(context["binding_id"], "1.0.0")

    def test_reject_unknown_binding(self):
        context = _build_context()
        _publish(context, "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError):
            context["release_service"].release("binding-missing", "1.0.0")

    def test_reject_unknown_version(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError):
            context["release_service"].release(context["binding_id"], "does-not-exist")

    def test_reject_blank_ids(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError):
            context["release_service"].release("   ", "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError):
            context["release_service"].release(context["binding_id"], None)


class TestImmutableReleaseHistory:
    def test_immutable_release_history(self):
        context = _build_context()
        _publish(context, "1.0.0")

        released = context["release_service"].release(context["binding_id"], "1.0.0").release

        with pytest.raises(dataclasses.FrozenInstanceError):
            released.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RETIRED

        retired_result = context["release_service"].retire(context["binding_id"], "1.0.0")

        assert released.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RELEASED
        assert retired_result.release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus.RETIRED
        assert retired_result.release.release_id == released.release_id


class TestDeploymentAllowedOnlyForReleasedVersions:
    def test_deployment_gate_reflects_release_status(self):
        context = _build_context()
        _publish(context, "1.0.0")

        def deployable(binding_id, version):
            return context["release_service"].is_released(binding_id, version)

        assert deployable(context["binding_id"], "1.0.0") is False

        context["release_service"].release(context["binding_id"], "1.0.0")
        assert deployable(context["binding_id"], "1.0.0") is True

        context["release_service"].retire(context["binding_id"], "1.0.0")
        assert deployable(context["binding_id"], "1.0.0") is False
