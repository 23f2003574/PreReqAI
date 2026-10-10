import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionHistory,
)


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        ),
        initial_state,
    )


def _build_template(template_id="standard-registration", template_name="Standard Registration", policy=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
        template_id=template_id,

        template_name=template_name,

        description="A standard registration lifecycle policy.",

        lifecycle_policy=(
            policy
            if policy is not None
            else _build_policy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            )
        ),
    )


def _build_version(version_id, policy=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion(
        version=version_id,

        lifecycle_policy=(
            policy
            if policy is not None
            else _build_policy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            )
        ),

        created_at=datetime.now(timezone.utc),
    )


class TestValidTemplate:
    """A fully populated template has no violations."""

    def test_valid_template(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate(
            _build_template()
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidationResult,
        )
        assert result.valid is True
        assert result.violations == ()


class TestMissingTemplateId:
    """A template with a blank template ID is invalid."""

    def test_missing_template_id(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate(
            _build_template(
                template_id="   ",
            )
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_TEMPLATE_ID"
            for violation
            in result.violations
        )


class TestMissingTemplateName:
    """A template with a blank template name is invalid."""

    def test_missing_template_name(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate(
            _build_template(
                template_name="",
            )
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_TEMPLATE_NAME"
            for violation
            in result.violations
        )


class TestMissingLifecyclePolicy:
    """A template with a missing lifecycle policy is invalid."""

    def test_missing_lifecycle_policy(self):
        template = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
            template_id="standard-registration",

            template_name="Standard Registration",

            description="A standard registration lifecycle policy.",

            lifecycle_policy=None,
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate(
            template
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_LIFECYCLE_POLICY"
            for violation
            in result.violations
        )


class TestMultipleViolations:
    """Every violation on a template is accumulated, not just the first."""

    def test_multiple_violations(self):
        template = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
            template_id="",

            template_name="",

            description="",

            lifecycle_policy=None,
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate(
            template
        )

        assert result.valid is False
        assert {
            violation.code
            for violation
            in result.violations
        } == {
            "MISSING_TEMPLATE_ID",
            "MISSING_TEMPLATE_NAME",
            "MISSING_LIFECYCLE_POLICY",
        }


class TestDuplicateVersions:
    """A history with duplicate version identifiers is invalid."""

    def test_duplicate_versions(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionHistory(
            template_id="standard-registration",

            current_version="1.0.0",

            versions=(
                _build_version("1.0.0"),
                _build_version("1.0.0"),
            ),
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate_history(
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
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionHistory(
            template_id="standard-registration",

            current_version="",

            versions=(
                _build_version("1.0.0"),
            ),
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate_history(
            history
        )

        assert result.valid is False
        assert any(
            violation.code == "MISSING_CURRENT_VERSION"
            for violation
            in result.violations
        )

    def test_current_version_not_in_history(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionHistory(
            template_id="standard-registration",

            current_version="9.9.9",

            versions=(
                _build_version("1.0.0"),
            ),
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate_history(
            history
        )

        assert result.valid is False
        assert any(
            violation.code == "CURRENT_VERSION_NOT_IN_HISTORY"
            for violation
            in result.violations
        )

    def test_none_history(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate_history(
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
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate_version(
            _build_version("1.0.0")
        )

        assert result.valid is True
        assert result.violations == ()


class TestValidHistory:
    """A well-formed history has no violations."""

    def test_valid_history(self):
        history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersionHistory(
            template_id="standard-registration",

            current_version="1.0.0",

            versions=(
                _build_version("1.0.0"),
                _build_version("1.1.0"),
            ),
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate_history(
            history
        )

        assert result.valid is True
        assert result.violations == ()


class TestImmutableResults:
    """A validation result and its violations cannot be reassigned."""

    def test_immutable_results(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate(
            _build_template(
                template_id="",
            )
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.valid = True

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].code = "CHANGED"

    def test_does_not_mutate_input_template(self):
        template = _build_template(
            template_id="",
        )

        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateValidator().validate(
            template
        )

        assert template.template_id == ""
