import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService,
)


def _build_version(version_id, policy_identifiers=("policy-a", "policy-b")):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
        version=version_id,

        policy_identifiers=policy_identifiers,

        created_at=datetime.now(timezone.utc),
    )


class TestPublishFirstVersion:
    """The first version published for a profile becomes current."""

    def test_publish_first_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        version = _build_version("1.0.0")

        service.publish("development", version)

        assert service.latest("development") is version


class TestPublishMultipleVersions:
    """Multiple versions can be published for the same profile."""

    def test_publish_multiple_versions(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        first = _build_version("1.0.0")
        second = _build_version("1.1.0")
        third = _build_version("2.0.0")

        service.publish("development", first)
        service.publish("development", second)
        service.publish("development", third)

        history = service.history("development")

        assert [
            published.version
            for published in history.versions
        ] == ["1.0.0", "1.1.0", "2.0.0"]
        assert history.current_version == "2.0.0"


class TestLatestVersion:
    """latest() returns the current version, not just the most recent one."""

    def test_latest_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        service.publish("development", _build_version("1.0.0"))
        second = _build_version("1.1.0")
        service.publish("development", second)

        assert service.latest("development") is second


class TestLatestVersionMissingProfile:
    """latest() returns None for a profile with no published versions."""

    def test_latest_version_missing_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

        assert service.latest("does-not-exist") is None


class TestLookupSpecificVersion:
    """find() looks up a specific published version by identifier."""

    def test_lookup_specific_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        first = _build_version("1.0.0")
        second = _build_version("1.1.0")
        service.publish("development", first)
        service.publish("development", second)

        assert service.find("development", "1.0.0") is first
        assert service.find("development", "1.1.0") is second


class TestLookupMissingVersion:
    """find() returns None for a version that was never published."""

    def test_lookup_missing_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        service.publish("development", _build_version("1.0.0"))

        assert service.find("development", "9.9.9") is None
        assert service.find("does-not-exist", "1.0.0") is None


class TestVersionHistory:
    """history() returns the full, ordered version history for a profile."""

    def test_version_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        first = _build_version("1.0.0")
        second = _build_version("1.1.0")
        service.publish("development", first)
        service.publish("development", second)

        history = service.history("development")

        assert history.profile_id == "development"
        assert history.versions == (first, second)


class TestVersionHistoryMissingProfile:
    """history() returns None for a profile with no published versions."""

    def test_version_history_missing_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

        assert service.history("does-not-exist") is None


class TestRollback:
    """Rolling back moves current_version without deleting history."""

    def test_rollback(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        first = _build_version("1.0.0")
        second = _build_version("1.1.0")
        third = _build_version("2.0.0")
        service.publish("development", first)
        service.publish("development", second)
        service.publish("development", third)

        service.rollback("development", "1.0.0")

        assert service.latest("development") is first

        history = service.history("development")

        assert history.current_version == "1.0.0"
        assert [
            published.version
            for published in history.versions
        ] == ["1.0.0", "1.1.0", "2.0.0"]


class TestRollbackMissingVersion:
    """Rolling back to a version that was never published is rejected."""

    def test_rollback_missing_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        service.publish("development", _build_version("1.0.0"))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError
        ):
            service.rollback("development", "9.9.9")


class TestRollbackMissingProfile:
    """Rolling back a profile with no published versions is rejected."""

    def test_rollback_missing_profile(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError
        ):
            service.rollback("does-not-exist", "1.0.0")


class TestImmutableHistory:
    """A previously read history is unaffected by later publications."""

    def test_immutable_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        service.publish("development", _build_version("1.0.0"))

        snapshot = service.history("development")

        service.publish("development", _build_version("1.1.0"))

        assert len(snapshot.versions) == 1
        assert len(service.history("development").versions) == 2

        with pytest.raises(dataclasses.FrozenInstanceError):
            snapshot.current_version = "1.1.0"


class TestRejectDuplicateVersion:
    """Publishing a second version with the same identifier is rejected."""

    def test_reject_duplicate_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        service.publish("development", _build_version("1.0.0"))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError
        ):
            service.publish("development", _build_version("1.0.0"))

        assert len(service.history("development").versions) == 1


class TestRejectNoneVersion:
    """Publishing a None version is rejected."""

    def test_reject_none_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError
        ):
            service.publish("development", None)


class TestRejectBlankProfileId:
    """Publishing under a blank profile ID is rejected."""

    def test_reject_blank_profile_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError
        ):
            service.publish("   ", _build_version("1.0.0"))


class TestRejectBlankVersionIdentifier:
    """Publishing a version with a blank version identifier is rejected."""

    def test_reject_blank_version_identifier(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError
        ):
            service.publish("development", _build_version("   "))


class TestRejectMissingPolicyIdentifiers:
    """Publishing a version with a missing policy identifier collection is rejected."""

    def test_reject_missing_policy_identifiers(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()
        version = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
            version="1.0.0",

            policy_identifiers=None,

            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError
        ):
            service.publish("development", version)


class TestRejectWrongType:
    """Publishing a non-version object is rejected."""

    def test_reject_wrong_type(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionError
        ):
            service.publish("development", "not-a-version")
