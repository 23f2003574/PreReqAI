import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion,
)


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        ),
        initial_state,
    )


class TestBuildVersion:
    """A version can be built from its fields."""

    def test_build_version(self):
        policy = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        )
        created_at = datetime.now(timezone.utc)

        version = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion(
            version="1.0.0",

            lifecycle_policy=policy,

            created_at=created_at,
        )

        assert version.version == "1.0.0"
        assert version.lifecycle_policy is policy
        assert version.created_at == created_at


class TestImmutableVersion:
    """A built version cannot have its fields reassigned."""

    def test_immutable_version(self):
        version = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateVersion(
            version="1.0.0",

            lifecycle_policy=_build_policy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ),

            created_at=datetime.now(timezone.utc),
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            version.version = "2.0.0"
