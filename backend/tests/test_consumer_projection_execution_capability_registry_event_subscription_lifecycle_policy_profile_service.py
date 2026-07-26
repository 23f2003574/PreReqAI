import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService,
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
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
        profile = _build_profile("development")

        service.register(profile)

        assert service.find("development") is profile


class TestReplaceProfile:
    """An already-registered profile can be replaced in place."""

    def test_replace_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
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
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError
        ):
            service.replace(_build_profile("does-not-exist"))


class TestRemoveProfile:
    """Removing an existing profile removes it."""

    def test_remove_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
        service.register(_build_profile("production"))

        service.remove("production")

        assert service.find("production") is None
        assert service.contains("production") is False


class TestRemoveMissingProfile:
    """Removing a profile ID that was never registered is rejected."""

    def test_remove_missing_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError
        ):
            service.remove("does-not-exist")


class TestLookupExistingProfile:
    """An existing profile is found by find()."""

    def test_lookup_existing_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
        profile = _build_profile("development")
        service.register(profile)

        assert service.find("development") is profile


class TestLookupMissingProfile:
    """A missing profile is not found by find()."""

    def test_lookup_missing_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

        assert service.find("does-not-exist") is None


class TestContains:
    """contains() reports registration state accurately."""

    def test_contains(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
        service.register(_build_profile("development"))

        assert service.contains("development") is True
        assert service.contains("does-not-exist") is False


class TestListOrdering:
    """Profiles are listed in registration order."""

    def test_list_ordering(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
        service.register(_build_profile("zeta"))
        service.register(_build_profile("alpha"))
        service.register(_build_profile("mid"))

        assert [
            profile.profile_id
            for profile in service.list()
        ] == ["zeta", "alpha", "mid"]


class TestImmutableCollection:
    """A previously listed tuple is unaffected by later registrations."""

    def test_immutable_collection(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
        service.register(_build_profile("development"))

        listed = service.list()

        service.register(_build_profile("staging"))

        assert len(listed) == 1
        assert len(service.list()) == 2


class TestRejectNoneProfile:
    """Registering a None profile is rejected."""

    def test_reject_none_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError
        ):
            service.register(None)


class TestRejectDuplicateProfileId:
    """Registering a second profile with the same ID is rejected."""

    def test_reject_duplicate_profile_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()
        service.register(_build_profile("development"))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError
        ):
            service.register(_build_profile("development"))

        assert len(service.list()) == 1


class TestRejectBlankProfileId:
    """Building a profile with a blank profile ID is rejected."""

    def test_reject_blank_profile_id(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError
        ):
            _build_profile("   ")


class TestRejectBlankProfileName:
    """Building a profile with a blank profile name is rejected."""

    def test_reject_blank_profile_name(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
                profile_id="development",

                profile_name="   ",

                description="Development profile.",

                policy_identifiers=("policy-a",),
            )


class TestRejectDuplicatePolicyIdentifiers:
    """Building a profile with duplicate policy identifiers is rejected."""

    def test_reject_duplicate_policy_identifiers(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError
        ):
            _build_profile(
                "development",

                policy_identifiers=("policy-a", "policy-a"),
            )


class TestRejectWrongType:
    """Registering a non-profile object is rejected."""

    def test_reject_wrong_type(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError
        ):
            service.register("not-a-profile")
