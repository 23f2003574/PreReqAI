import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService,
)


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        ),
        initial_state,
    )


def _build_version(version_id, initial_state=None, policy=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion(
        version=version_id,

        lifecycle_policy=(
            policy
            if policy is not None
            else _build_policy(
                initial_state
                or ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            )
        ),

        created_at=datetime.now(timezone.utc),
    )


class TestPublishFirstVersion:
    """The first version published for a template becomes current."""

    def test_publish_first_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        version = _build_version("1.0.0")

        service.publish("standard-registration", version)

        assert service.latest("standard-registration") is version


class TestPublishMultipleVersions:
    """Multiple versions can be published for the same template."""

    def test_publish_multiple_versions(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        first = _build_version("1.0.0")
        second = _build_version("1.1.0")
        third = _build_version("2.0.0")

        service.publish("standard-registration", first)
        service.publish("standard-registration", second)
        service.publish("standard-registration", third)

        history = service.history("standard-registration")

        assert [
            published.version
            for published in history.versions
        ] == ["1.0.0", "1.1.0", "2.0.0"]
        assert history.current_version == "2.0.0"


class TestLatestVersion:
    """latest() returns the current version, not just the most recent one."""

    def test_latest_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        service.publish("standard-registration", _build_version("1.0.0"))
        second = _build_version("1.1.0")
        service.publish("standard-registration", second)

        assert service.latest("standard-registration") is second


class TestLatestVersionMissingTemplate:
    """latest() returns None for a template with no published versions."""

    def test_latest_version_missing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()

        assert service.latest("does-not-exist") is None


class TestLookupSpecificVersion:
    """find() looks up a specific published version by identifier."""

    def test_lookup_specific_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        first = _build_version("1.0.0")
        second = _build_version("1.1.0")
        service.publish("standard-registration", first)
        service.publish("standard-registration", second)

        assert service.find("standard-registration", "1.0.0") is first
        assert service.find("standard-registration", "1.1.0") is second


class TestLookupMissingVersion:
    """find() returns None for a version that was never published."""

    def test_lookup_missing_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        service.publish("standard-registration", _build_version("1.0.0"))

        assert service.find("standard-registration", "9.9.9") is None
        assert service.find("does-not-exist", "1.0.0") is None


class TestVersionHistory:
    """history() returns the full, ordered version history for a template."""

    def test_version_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        first = _build_version("1.0.0")
        second = _build_version("1.1.0")
        service.publish("standard-registration", first)
        service.publish("standard-registration", second)

        history = service.history("standard-registration")

        assert history.template_id == "standard-registration"
        assert history.versions == (first, second)


class TestVersionHistoryMissingTemplate:
    """history() returns None for a template with no published versions."""

    def test_version_history_missing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()

        assert service.history("does-not-exist") is None


class TestRollback:
    """Rolling back moves current_version without deleting history."""

    def test_rollback(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        first = _build_version("1.0.0")
        second = _build_version("1.1.0")
        third = _build_version("2.0.0")
        service.publish("standard-registration", first)
        service.publish("standard-registration", second)
        service.publish("standard-registration", third)

        service.rollback("standard-registration", "1.0.0")

        assert service.latest("standard-registration") is first

        history = service.history("standard-registration")

        assert history.current_version == "1.0.0"
        assert [
            published.version
            for published in history.versions
        ] == ["1.0.0", "1.1.0", "2.0.0"]


class TestRollbackMissingVersion:
    """Rolling back to a version that was never published is rejected."""

    def test_rollback_missing_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        service.publish("standard-registration", _build_version("1.0.0"))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError
        ):
            service.rollback("standard-registration", "9.9.9")


class TestRollbackMissingTemplate:
    """Rolling back a template with no published versions is rejected."""

    def test_rollback_missing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError
        ):
            service.rollback("does-not-exist", "1.0.0")


class TestImmutableHistory:
    """A previously read history is unaffected by later publications."""

    def test_immutable_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        service.publish("standard-registration", _build_version("1.0.0"))

        snapshot = service.history("standard-registration")

        service.publish("standard-registration", _build_version("1.1.0"))

        assert len(snapshot.versions) == 1
        assert len(service.history("standard-registration").versions) == 2

        with pytest.raises(dataclasses.FrozenInstanceError):
            snapshot.current_version = "1.1.0"


class TestRejectDuplicateVersion:
    """Publishing a second version with the same identifier is rejected."""

    def test_reject_duplicate_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        service.publish("standard-registration", _build_version("1.0.0"))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError
        ):
            service.publish("standard-registration", _build_version("1.0.0"))

        assert len(service.history("standard-registration").versions) == 1


class TestRejectNoneVersion:
    """Publishing a None version is rejected."""

    def test_reject_none_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError
        ):
            service.publish("standard-registration", None)


class TestRejectBlankTemplateId:
    """Publishing under a blank template ID is rejected."""

    def test_reject_blank_template_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError
        ):
            service.publish("   ", _build_version("1.0.0"))


class TestRejectBlankVersionIdentifier:
    """Publishing a version with a blank version identifier is rejected."""

    def test_reject_blank_version_identifier(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError
        ):
            service.publish("standard-registration", _build_version("   "))


class TestRejectMissingLifecyclePolicy:
    """Publishing a version with a missing lifecycle policy is rejected."""

    def test_reject_missing_lifecycle_policy(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()
        version = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion(
            version="1.0.0",

            lifecycle_policy=None,

            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError
        ):
            service.publish("standard-registration", version)


class TestRejectWrongType:
    """Publishing a non-version object is rejected."""

    def test_reject_wrong_type(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionError
        ):
            service.publish("standard-registration", "not-a-version")
