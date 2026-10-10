import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
)


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.UNREGISTERED,
        ),
        initial_state,
    )


class TestBuildTemplate:
    """A template can be built from its fields."""

    def test_build_template(self):
        policy = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        )

        template = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
            template_id="standard-registration",

            template_name="Standard Registration",

            description="A standard registration lifecycle policy.",

            lifecycle_policy=policy,
        )

        assert template.template_id == "standard-registration"
        assert template.template_name == "Standard Registration"
        assert template.lifecycle_policy is policy


class TestImmutableTemplate:
    """A built template cannot have its fields reassigned."""

    def test_immutable_template(self):
        template = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
            template_id="standard-registration",

            template_name="Standard Registration",

            description="A standard registration lifecycle policy.",

            lifecycle_policy=_build_policy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            template.template_id = "changed"
