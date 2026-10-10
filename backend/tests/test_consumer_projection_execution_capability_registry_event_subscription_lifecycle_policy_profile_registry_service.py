import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistrySnapshot,
)


def _build_profile(profile_id, policy_identifiers=("policy-a", "policy-b")):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,

        profile_name=profile_id,

        description=f"Profile {profile_id}.",

        policy_identifiers=policy_identifiers,
    )


class TestRegisterProfile:
    """A single profile can be registered and later found."""

    def test_register_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        profile = _build_profile("development")

        service.register(profile)

        assert service.find("development") is profile


class TestReplaceProfile:
    """An already-registered profile can be replaced in place."""

    def test_replace_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        service.register(_build_profile("zeta"))
        service.register(_build_profile("staging"))
        service.register(_build_profile("alpha"))

        replacement = _build_profile("staging", policy_identifiers=("policy-c",))

        service.replace(replacement)

        assert service.find("staging") is replacement
        assert [
            profile.profile_id
            for profile in service.list()
        ] == ["zeta", "staging", "alpha"]


class TestReplaceMissingProfile:
    """Replacing a profile that was never registered is rejected."""

    def test_replace_missing_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError
        ):
            service.replace(_build_profile("does-not-exist"))


class TestUnregisterProfile:
    """Unregistering an existing profile removes it."""

    def test_unregister_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        service.register(_build_profile("development"))

        service.unregister("development")

        assert service.find("development") is None
        assert service.contains("development") is False


class TestUnregisterMissingProfile:
    """Unregistering a profile ID that was never registered is rejected."""

    def test_unregister_missing_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError
        ):
            service.unregister("does-not-exist")


class TestLookupExistingProfile:
    """An existing profile is found by find()."""

    def test_lookup_existing_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        profile = _build_profile("development")
        service.register(profile)

        assert service.find("development") is profile


class TestLookupMissingProfile:
    """A missing profile is not found by find()."""

    def test_lookup_missing_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()

        assert service.find("does-not-exist") is None


class TestContains:
    """contains() reports registration state accurately."""

    def test_contains(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        service.register(_build_profile("development"))

        assert service.contains("development") is True
        assert service.contains("does-not-exist") is False


class TestListOrdering:
    """Profiles are listed in registration order."""

    def test_list_ordering(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        service.register(_build_profile("zeta"))
        service.register(_build_profile("alpha"))
        service.register(_build_profile("mid"))

        assert [
            profile.profile_id
            for profile in service.list()
        ] == ["zeta", "alpha", "mid"]


class TestSnapshotGeneration:
    """snapshot() reflects the registry's current state."""

    def test_snapshot_generation(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        service.register(_build_profile("zeta"))
        service.register(_build_profile("alpha"))

        snapshot = service.snapshot()

        assert isinstance(
            snapshot,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistrySnapshot,
        )
        assert snapshot.profile_count == 2
        assert snapshot.profile_identifiers == ("zeta", "alpha")

        service.register(_build_profile("mid"))

        assert snapshot.profile_count == 2
        assert service.snapshot().profile_count == 3


class TestImmutableRegistry:
    """A previously listed snapshot is unaffected by later registrations."""

    def test_immutable_registry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        service.register(_build_profile("development"))

        listed = service.list()

        service.register(_build_profile("staging"))

        assert len(listed) == 1
        assert len(service.list()) == 2


class TestRejectNoneProfile:
    """Registering a None profile is rejected."""

    def test_reject_none_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError
        ):
            service.register(None)


class TestRejectDuplicateProfileId:
    """Registering a second profile with the same ID is rejected."""

    def test_reject_duplicate_profile_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()
        service.register(_build_profile("development"))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError
        ):
            service.register(_build_profile("development"))

        assert len(service.list()) == 1


class TestRejectBlankIdentifier:
    """Operating with a blank profile ID is rejected."""

    def test_reject_blank_identifier(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError
        ):
            service.unregister("   ")


class TestRejectWrongType:
    """Registering a non-profile object is rejected."""

    def test_reject_wrong_type(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryError
        ):
            service.register("not-a-profile")
