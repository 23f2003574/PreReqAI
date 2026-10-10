import dataclasses

from datetime import datetime, timezone

from types import SimpleNamespace

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionHistory,
)


def _build_profile(profile_id="development", profile_name="Development", policy_identifiers=("policy-a", "policy-b")):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile(
        profile_id=profile_id,

        profile_name=profile_name,

        description="A development lifecycle policy profile.",

        policy_identifiers=policy_identifiers,
    )


def _build_malformed_profile(profile_id="development", profile_name="Development", policy_identifiers=("policy-a", "policy-b")):
    # The profile model self-validates in __post_init__, so a
    # malformed, invalid-shape stand-in is used to exercise the
    # validator against inputs the model itself would reject at
    # construction time.
    return SimpleNamespace(
        profile_id=profile_id,

        profile_name=profile_name,

        policy_identifiers=policy_identifiers,
    )


def _build_version(version_id, policy_identifiers=("policy-a",)):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersion(
        version=version_id,

        policy_identifiers=policy_identifiers,

        created_at=datetime.now(timezone.utc),
    )


class TestValidProfile:
    """A fully populated profile has no violations."""

    def test_valid_profile(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate(
            _build_profile()
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationResult,
        )
        assert result.valid is True
        assert result.violations == ()


class TestMissingProfileId:
    """A profile with a blank profile ID is invalid."""

    def test_missing_profile_id(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate(
            _build_malformed_profile(
                profile_id="   ",
            )
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_PROFILE_ID"
            for violation
            in result.violations
        )


class TestMissingProfileName:
    """A profile with a blank profile name is invalid."""

    def test_missing_profile_name(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate(
            _build_malformed_profile(
                profile_name="",
            )
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_PROFILE_NAME"
            for violation
            in result.violations
        )


class TestDuplicatePolicyIdentifiers:
    """A profile with duplicate policy identifiers is invalid."""

    def test_duplicate_policy_identifiers(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate(
            _build_malformed_profile(
                policy_identifiers=("policy-a", "policy-a"),
            )
        )

        assert result.valid is False
        assert any(
            violation.code == "DUPLICATE_POLICY_IDENTIFIER"
            for violation
            in result.violations
        )


class TestMultipleViolations:
    """Every violation on a profile is accumulated, not just the first."""

    def test_multiple_violations(self):
        profile = _build_malformed_profile(
            profile_id="",

            profile_name="",

            policy_identifiers=("policy-a", "policy-a"),
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate(
            profile
        )

        assert result.valid is False
        assert {
            violation.code
            for violation
            in result.violations
        } == {
            "MISSING_PROFILE_ID",
            "MISSING_PROFILE_NAME",
            "DUPLICATE_POLICY_IDENTIFIER",
        }


class TestDuplicateVersions:
    """A history with duplicate version identifiers is invalid."""

    def test_duplicate_versions(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionHistory(
            profile_id="development",

            current_version="1.0.0",

            versions=(
                _build_version("1.0.0"),
                _build_version("1.0.0"),
            ),
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate_history(
            history
        )

        assert result.valid is False
        assert any(
            violation.code == "DUPLICATE_VERSION"
            for violation
            in result.violations
        )


class TestInvalidHistory:
    """A history missing a current version, or pointing at an unpublished one, is invalid."""

    def test_missing_current_version(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionHistory(
            profile_id="development",

            current_version="",

            versions=(
                _build_version("1.0.0"),
            ),
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate_history(
            history
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_CURRENT_VERSION"
            for violation
            in result.violations
        )

    def test_current_version_not_in_history(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionHistory(
            profile_id="development",

            current_version="9.9.9",

            versions=(
                _build_version("1.0.0"),
            ),
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate_history(
            history
        )

        assert result.valid is False
        assert any(
            violation.code == "CURRENT_VERSION_NOT_IN_HISTORY"
            for violation
            in result.violations
        )

    def test_none_history(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate_history(
            None
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_HISTORY"
            for violation
            in result.violations
        )


class TestValidVersion:
    """A fully populated version has no violations."""

    def test_valid_version(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate_version(
            _build_version("1.0.0")
        )

        assert result.valid is True
        assert result.violations == ()


class TestValidHistory:
    """A well-formed history has no violations."""

    def test_valid_history(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileVersionHistory(
            profile_id="development",

            current_version="1.0.0",

            versions=(
                _build_version("1.0.0"),
                _build_version("1.1.0"),
            ),
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate_history(
            history
        )

        assert result.valid is True
        assert result.violations == ()


class TestImmutableResults:
    """A validation result and its violations cannot be reassigned."""

    def test_immutable_results(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate(
            _build_malformed_profile(
                profile_id="",
            )
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.valid = True

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].code = "CHANGED"

    def test_does_not_mutate_input_profile(self):
        profile = _build_malformed_profile(
            profile_id="",
        )

        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate(
            profile
        )

        assert profile.profile_id == ""


class TestRejectNoneInputs:
    """Validating None for any subject returns an invalid result rather than raising."""

    def test_reject_none_profile(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate(
            None
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_PROFILE"
            for violation
            in result.violations
        )

    def test_reject_none_version(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate_version(
            None
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_VERSION"
            for violation
            in result.violations
        )

    def test_reject_none_history(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidator().validate_history(
            None
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_HISTORY"
            for violation
            in result.violations
        )
