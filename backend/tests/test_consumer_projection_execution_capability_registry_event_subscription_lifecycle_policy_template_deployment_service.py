import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService,
)


_STATE = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (_STATE.REGISTERED, _STATE.ACTIVE),

        initial_state,
    )


def _build_template(template_id, policy=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
        template_id=template_id,

        template_name=template_id,

        description=f"Template {template_id}.",

        lifecycle_policy=(
            policy
            if policy is not None
            else _build_policy(
                _STATE.REGISTERED,
            )
        ),
    )


def _build_registry(*templates):
    registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()

    for template in templates:

        registry.register(
            template
        )

    return registry


class TestDeployNewPolicy:
    """A template not yet deployed can be deployed."""

    def test_deploy_new_policy(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()
        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
            template_id="standard-registration",

            target_registry=registry,
        )

        result = service.deploy(
            request
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentResult,
        )
        assert isinstance(
            result.deployed_policy,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
        )
        assert result.deployment_successful is True
        assert result.template_id == "standard-registration"
        assert registry.find("standard-registration").lifecycle_policy == result.deployed_policy


class TestReplaceExistingDeployment:
    """deploy_or_replace() re-deploys a template already deployed once."""

    def test_replace_existing_deployment(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()
        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
            template_id="standard-registration",

            target_registry=registry,
        )

        first = service.deploy(
            request
        )
        second = service.deploy_or_replace(
            request
        )

        assert first.deployment_successful is True
        assert second.deployment_successful is True
        assert second.deployed_policy is not first.deployed_policy
        assert registry.find("standard-registration").lifecycle_policy == second.deployed_policy


class TestCanDeploy:
    """can_deploy() reports deployability without raising or deploying."""

    def test_can_deploy_true(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()
        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
            template_id="standard-registration",

            target_registry=registry,
        )

        assert service.can_deploy(request) is True

    def test_can_deploy_false_missing_template(self):
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()
        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
            template_id="does-not-exist",

            target_registry=registry,
        )

        assert service.can_deploy(request) is False

    def test_can_deploy_false_already_deployed(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()
        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
            template_id="standard-registration",

            target_registry=registry,
        )

        service.deploy(
            request
        )

        assert service.can_deploy(request) is False


class TestDeploymentConflict:
    """Deploying an already-deployed template ID with deploy() is rejected."""

    def test_deployment_conflict(self):
        registry = _build_registry(
            _build_template("standard-registration")
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()
        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
            template_id="standard-registration",

            target_registry=registry,
        )

        service.deploy(
            request
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError
        ):
            service.deploy(
                request
            )


class TestImmutableTemplateRegistry:
    """Deployment never disturbs other entries in the target registry."""

    def test_immutable_template_registry(self):
        registry = _build_registry(
            _build_template("zeta"),

            _build_template("standard-registration"),

            _build_template("alpha"),
        )
        zeta_before = registry.find("zeta")
        alpha_before = registry.find("alpha")
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()
        request = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
            template_id="standard-registration",

            target_registry=registry,
        )

        service.deploy(
            request
        )

        assert registry.find("zeta") is zeta_before
        assert registry.find("alpha") is alpha_before
        assert [
            template.template_id
            for template in registry.list()
        ] == ["zeta", "standard-registration", "alpha"]


class TestRejectInvalidInputs:
    """None requests, blank identifiers, and invalid registries are rejected."""

    def test_reject_none_request(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError
        ):
            service.deploy(
                None
            )

    def test_reject_missing_template(self):
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
                    template_id="does-not-exist",

                    target_registry=registry,
                )
            )

    def test_reject_blank_template_id(self):
        registry = _build_registry()
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
                    template_id="   ",

                    target_registry=registry,
                )
            )

    def test_reject_none_target_registry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
                    template_id="standard-registration",

                    target_registry=None,
                )
            )

    def test_reject_invalid_target_registry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
                    template_id="standard-registration",

                    target_registry="not-a-registry",
                )
            )

    def test_reject_invalid_template(self):
        broken_template = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
            template_id="broken-template",

            template_name="",

            description="",

            lifecycle_policy=None,
        )
        registry = _build_registry(
            broken_template
        )
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentError
        ):
            service.deploy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRequest(
                    template_id="broken-template",

                    target_registry=registry,
                )
            )
