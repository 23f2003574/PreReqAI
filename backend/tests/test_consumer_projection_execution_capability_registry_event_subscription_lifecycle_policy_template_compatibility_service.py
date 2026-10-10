import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService,
)


def _build_policy(allowed_states, initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        allowed_states,

        initial_state,
    )


def _build_template(allowed_states, initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
        template_id="standard-registration",

        template_name="Standard Registration",

        description="A standard registration lifecycle policy.",

        lifecycle_policy=_build_policy(
            allowed_states,

            initial_state,
        ),
    )


_STATE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState


class TestCompatibleTemplate:
    """A template whose states cover the existing policy is compatible."""

    def test_compatible_template(self):
        template = _build_template(
            (_STATE.REGISTERED, _STATE.ACTIVE, _STATE.SUSPENDED),

            _STATE.REGISTERED,
        )
        existing_policy = _build_policy(
            (_STATE.REGISTERED, _STATE.ACTIVE),

            _STATE.REGISTERED,
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        result = service.check(
            template,

            existing_policy,
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityResult,
        )
        assert result.compatible is True
        assert result.incompatible_fields == ()
        assert result.reason is None


class TestIncompatibleTemplate:
    """A template missing one of the existing policy's states is incompatible."""

    def test_incompatible_template(self):
        template = _build_template(
            (_STATE.REGISTERED, _STATE.ACTIVE),

            _STATE.REGISTERED,
        )
        existing_policy = _build_policy(
            (_STATE.REGISTERED, _STATE.ACTIVE, _STATE.SUSPENDED),

            _STATE.REGISTERED,
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        result = service.check(
            template,

            existing_policy,
        )

        assert result.compatible is False
        assert "allowed_states_superset" in result.incompatible_fields
        assert result.reason is not None


class TestMultipleIncompatibilities:
    """Every failing rule is reported, not just the first."""

    def test_multiple_incompatibilities(self):
        template = _build_template(
            (_STATE.REGISTERED,),

            _STATE.REGISTERED,
        )
        existing_policy = _build_policy(
            (_STATE.REGISTERED, _STATE.ACTIVE, _STATE.SUSPENDED),

            _STATE.SUSPENDED,
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        result = service.check(
            template,

            existing_policy,
        )

        assert result.compatible is False
        assert set(result.incompatible_fields) == {
            "allowed_states_superset",
            "initial_state_supported",
        }


class TestSupports:
    """supports() reports compatibility as a boolean."""

    def test_supports_true(self):
        template = _build_template(
            (_STATE.REGISTERED, _STATE.ACTIVE),

            _STATE.REGISTERED,
        )
        existing_policy = _build_policy(
            (_STATE.REGISTERED,),

            _STATE.REGISTERED,
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        assert service.supports(
            template,

            existing_policy,
        ) is True

    def test_supports_false(self):
        template = _build_template(
            (_STATE.REGISTERED,),

            _STATE.REGISTERED,
        )
        existing_policy = _build_policy(
            (_STATE.REGISTERED, _STATE.ACTIVE),

            _STATE.REGISTERED,
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        assert service.supports(
            template,

            existing_policy,
        ) is False


class TestValidate:
    """validate() succeeds silently or raises, mirroring check()'s outcome."""

    def test_validate_success(self):
        template = _build_template(
            (_STATE.REGISTERED, _STATE.ACTIVE),

            _STATE.REGISTERED,
        )
        existing_policy = _build_policy(
            (_STATE.REGISTERED,),

            _STATE.REGISTERED,
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        assert service.validate(
            template,

            existing_policy,
        ) is None

    def test_validate_failure(self):
        template = _build_template(
            (_STATE.REGISTERED,),

            _STATE.REGISTERED,
        )
        existing_policy = _build_policy(
            (_STATE.REGISTERED, _STATE.ACTIVE),

            _STATE.REGISTERED,
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError
        ):
            service.validate(
                template,

                existing_policy,
            )


class TestImmutableResult:
    """A compatibility result cannot have its fields reassigned."""

    def test_immutable_result(self):
        template = _build_template(
            (_STATE.REGISTERED, _STATE.ACTIVE),

            _STATE.REGISTERED,
        )
        existing_policy = _build_policy(
            (_STATE.REGISTERED,),

            _STATE.REGISTERED,
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        result = service.check(
            template,

            existing_policy,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.compatible = False

    def test_does_not_mutate_inputs(self):
        template = _build_template(
            (_STATE.REGISTERED, _STATE.ACTIVE),

            _STATE.REGISTERED,
        )
        existing_policy = _build_policy(
            (_STATE.REGISTERED,),

            _STATE.REGISTERED,
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        service.check(
            template,

            existing_policy,
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            template.template_id = "changed"

        with pytest.raises(dataclasses.FrozenInstanceError):
            existing_policy.initial_state = _STATE.ACTIVE


class TestRejectInvalidInputs:
    """None templates, policies, and malformed rules are rejected."""

    def test_reject_none_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError
        ):
            service.check(
                None,

                _build_policy(
                    (_STATE.REGISTERED,),

                    _STATE.REGISTERED,
                ),
            )

    def test_reject_none_lifecycle_policy(self):
        template = _build_template(
            (_STATE.REGISTERED,),

            _STATE.REGISTERED,
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError
        ):
            service.check(
                template,

                None,
            )

    def test_reject_invalid_compatibility_rule(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService(
                rules=(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule(
                        rule_name="not_a_real_rule",

                        required=True,
                    ),
                ),
            )

    def test_reject_duplicate_rule_names(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService(
                rules=(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule(
                        rule_name="allowed_states_superset",

                        required=True,
                    ),
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityRule(
                        rule_name="allowed_states_superset",

                        required=False,
                    ),
                ),
            )

    def test_reject_none_rule(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateCompatibilityService(
                rules=(None,),
            )
