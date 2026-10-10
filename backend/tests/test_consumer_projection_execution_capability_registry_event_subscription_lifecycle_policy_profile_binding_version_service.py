import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver,
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


def _build_binding(binding_id, profile_id, capability_id="capability-a"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id=profile_id,
        capability_id=capability_id,
        created_at=datetime.now(timezone.utc),
    )


def _build_context(profile_id="profile-a", binding_id="binding-1"):
    profile_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
    profile_service.register(_build_profile(profile_id))

    binding_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    binding_registry.register(_build_binding(binding_id, profile_id))

    version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
    resolver = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver(profile_service)
    release_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileReleaseService(resolver, version_service)

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionService(
        binding_registry,
        version_service,
        release_service,
    )

    return service, binding_registry, version_service, release_service


def _publish_and_release(version_service, release_service, profile_id, version):
    version_service.publish(
        profile_id,
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
            version=version,
            policy_identifiers=(f"policy-{version}",),
            created_at=datetime.now(timezone.utc),
        ),
    )
    release_service.release(profile_id, version)


class TestResolvePinnedVersion:
    def test_resolve_pinned_version(self):
        service, _, version_service, release_service = _build_context()
        _publish_and_release(version_service, release_service, "profile-a", "1.0.0")

        service.pin_version("binding-1", "1.0.0")
        result = service.resolve_version("binding-1")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionResult)
        assert result.resolved is True
        assert result.version == "1.0.0"


class TestResolveLatestRelease:
    def test_resolve_latest_release_default(self):
        service, _, version_service, release_service = _build_context()
        _publish_and_release(version_service, release_service, "profile-a", "1.0.0")
        _publish_and_release(version_service, release_service, "profile-a", "2.0.0")

        result = service.resolve_version("binding-1")

        assert result.resolved is True
        assert result.version == "2.0.0"

    def test_resolve_latest_release_none_released(self):
        service, _, _, _ = _build_context()

        result = service.resolve_version("binding-1")

        assert result.resolved is False
        assert result.version is None


class TestSwitchPinnedAndLatest:
    def test_switch_between_pinned_and_latest(self):
        service, _, version_service, release_service = _build_context()
        _publish_and_release(version_service, release_service, "profile-a", "1.0.0")
        _publish_and_release(version_service, release_service, "profile-a", "2.0.0")

        service.pin_version("binding-1", "1.0.0")
        assert service.resolve_version("binding-1").version == "1.0.0"

        service.follow_latest("binding-1")
        assert service.resolve_version("binding-1").version == "2.0.0"

        service.pin_version("binding-1", "2.0.0")
        assert service.resolve_version("binding-1").version == "2.0.0"


class TestPinnedStatus:
    def test_pinned_status(self):
        service, _, version_service, release_service = _build_context()
        _publish_and_release(version_service, release_service, "profile-a", "1.0.0")

        assert service.is_pinned("binding-1") is False

        service.pin_version("binding-1", "1.0.0")
        assert service.is_pinned("binding-1") is True

        service.follow_latest("binding-1")
        assert service.is_pinned("binding-1") is False


class TestUnreleasedVersionRejection:
    def test_reject_unreleased_version(self):
        service, _, version_service, _ = _build_context()
        version_service.publish(
            "profile-a",
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
                version="1.0.0",
                policy_identifiers=("policy-1",),
                created_at=datetime.now(timezone.utc),
            ),
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError):
            service.pin_version("binding-1", "1.0.0")

    def test_reject_retired_version(self):
        service, _, version_service, release_service = _build_context()
        _publish_and_release(version_service, release_service, "profile-a", "1.0.0")
        release_service.retire("profile-a", "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError):
            service.pin_version("binding-1", "1.0.0")

    def test_reject_nonexistent_version(self):
        service, _, _, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError):
            service.pin_version("binding-1", "does-not-exist")

    def test_reject_unknown_binding(self):
        service, _, version_service, release_service = _build_context()
        _publish_and_release(version_service, release_service, "profile-a", "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError):
            service.pin_version("binding-missing", "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError):
            service.resolve_version("binding-missing")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError):
            service.follow_latest("binding-missing")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError):
            service.is_pinned("binding-missing")

    def test_reject_blank_ids(self):
        service, _, _, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError):
            service.resolve_version("   ")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingVersionError):
            service.pin_version("binding-1", None)


class TestImmutableResults:
    def test_immutable_result(self):
        service, _, version_service, release_service = _build_context()
        _publish_and_release(version_service, release_service, "profile-a", "1.0.0")

        result = service.resolve_version("binding-1")

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.resolved = False
