import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionService,
)


def _build_profile(profile_id, policy_identifiers=("policy-a", "policy-b")):
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


def _build_service(profile_id="development", versions=("1.0.0",)):
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

    service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationService(
        resolver,

        version_service,
    )

    return service, registry, version_service


class TestInstantiateSpecificVersion:
    """A specific published version can be instantiated by request."""

    def test_instantiate_specific_version(self):
        service, _, _ = _build_service(
            versions=("1.0.0", "1.1.0"),
        )

        result = service.instantiate(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest(
                profile_id="development",

                version="1.0.0",

                parameter_values={
                    "threshold": 5,
                },
            )
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationResult,
        )
        assert result.instantiated is True
        assert result.profile_instance.profile_id == "development"
        assert result.profile_instance.version == "1.0.0"
        assert result.profile_instance.parameter_values == {"threshold": 5}


class TestInstantiateLatestVersion:
    """instantiate_latest() instantiates the current version, not just any published one."""

    def test_instantiate_latest_version(self):
        service, _, version_service = _build_service(
            versions=("1.0.0", "1.1.0"),
        )

        result = service.instantiate_latest(
            "development"
        )

        assert result.profile_instance.version == version_service.latest("development").version
        assert result.profile_instance.version == "1.1.0"


class TestInstantiateWithDefaults:
    """Omitting parameter values falls back to an empty default mapping."""

    def test_instantiate_with_defaults(self):
        service, _, _ = _build_service()

        result = service.instantiate(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest(
                profile_id="development",

                version="1.0.0",

                parameter_values=None,
            )
        )

        assert result.instantiated is True
        assert dict(result.profile_instance.parameter_values) == {}


class TestPreviewSucceeds:
    """preview() reports True for a resolvable profile and published version."""

    def test_preview_succeeds(self):
        service, _, _ = _build_service()

        assert service.preview("development", "1.0.0") is True


class TestPreviewFailure:
    """preview() reports False without raising or creating an instance."""

    def test_preview_failure_missing_version(self):
        service, _, _ = _build_service()

        assert service.preview("development", "9.9.9") is False

    def test_preview_failure_missing_profile(self):
        service, _, _ = _build_service()

        assert service.preview("does-not-exist", "1.0.0") is False


class TestCanInstantiateTrue:
    """can_instantiate() reports True for a profile with at least one published version."""

    def test_can_instantiate_true(self):
        service, _, _ = _build_service()

        assert service.can_instantiate("development") is True


class TestCanInstantiateFalse:
    """can_instantiate() reports False for an unresolvable profile or one with no published versions."""

    def test_can_instantiate_false_missing_profile(self):
        service, _, _ = _build_service()

        assert service.can_instantiate("does-not-exist") is False

    def test_can_instantiate_false_no_published_versions(self):
        service, _, _ = _build_service(
            versions=(),
        )

        assert service.can_instantiate("development") is False


class TestImmutableInstantiationResult:
    """A returned instantiation result and its instance cannot be reassigned."""

    def test_immutable_instantiation_result(self):
        service, _, _ = _build_service()

        result = service.instantiate(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest(
                profile_id="development",

                version="1.0.0",

                parameter_values=None,
            )
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.instantiated = False

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.profile_instance.version = "9.9.9"

    def test_does_not_mutate_stored_profile(self):
        service, registry, _ = _build_service()

        service.instantiate(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest(
                profile_id="development",

                version="1.0.0",

                parameter_values={"threshold": 5},
            )
        )

        assert registry.find("development").policy_identifiers == ("policy-a", "policy-b")


class TestRejectNoneRequest:
    """Instantiating from a None request is rejected."""

    def test_reject_none_request(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError
        ):
            service.instantiate(None)


class TestRejectWrongRequestType:
    """Instantiating from a non-request object is rejected."""

    def test_reject_wrong_request_type(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError
        ):
            service.instantiate("not-a-request")


class TestRejectBlankProfileId:
    """Instantiating with a blank profile ID is rejected."""

    def test_reject_blank_profile_id(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError
        ):
            service.instantiate(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest(
                    profile_id="   ",

                    version="1.0.0",

                    parameter_values=None,
                )
            )


class TestRejectBlankVersion:
    """Instantiating with a blank version is rejected."""

    def test_reject_blank_version(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError
        ):
            service.instantiate(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest(
                    profile_id="development",

                    version="   ",

                    parameter_values=None,
                )
            )


class TestRejectMissingProfile:
    """Instantiating from an unresolvable profile ID is rejected."""

    def test_reject_missing_profile(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError
        ):
            service.instantiate(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest(
                    profile_id="does-not-exist",

                    version="1.0.0",

                    parameter_values=None,
                )
            )


class TestRejectMissingVersion:
    """Instantiating an unpublished version is rejected."""

    def test_reject_missing_version(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError
        ):
            service.instantiate(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest(
                    profile_id="development",

                    version="9.9.9",

                    parameter_values=None,
                )
            )


class TestRejectInvalidParameterValues:
    """Instantiating with non-mapping parameter values is rejected."""

    def test_reject_invalid_parameter_values(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError
        ):
            service.instantiate(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest(
                    profile_id="development",

                    version="1.0.0",

                    parameter_values="not-a-mapping",
                )
            )


class TestRejectBlankProfileIdOnHelperMethods:
    """instantiate_latest(), can_instantiate(), and preview() reject blank profile IDs."""

    def test_instantiate_latest_rejects_blank_profile_id(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError
        ):
            service.instantiate_latest("   ")

    def test_can_instantiate_rejects_blank_profile_id(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError
        ):
            service.can_instantiate("   ")

    def test_preview_rejects_blank_profile_id(self):
        service, _, _ = _build_service()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationError
        ):
            service.preview("   ", "1.0.0")
