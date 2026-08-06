from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session policy's configuration at the moment
    it was published, so later changes to the policy never alter what
    an already-published version says.

    The version is a value object only. It performs no publishing or
    resolution. Publishing, resolving, and rolling back versions are
    the responsibility of a session policy version service.

    Attributes:
        policy_id: The identifier of the policy this version was
            published for
        version: This version's number, unique within policy_id and
            strictly increasing with each publish or rollback
        configuration: The policy's configuration as it stood when
            this version was published
        created_at: When this version was published
    """

    policy_id: str

    version: int

    configuration: dict

    created_at: datetime

    def __post_init__(self):
        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                "Cannot build a session policy version with an empty or blank policy ID."
            )

        if self.version is None or isinstance(self.version, bool) or not isinstance(self.version, int) or self.version <= 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                f"Invalid session policy version number {self.version!r}; version must be a positive integer."
            )

        if self.configuration is None or not isinstance(self.configuration, dict) or not self.configuration:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                "Cannot build a session policy version with an empty or non-dict configuration."
            )

        for key in self.configuration:
            if key is None or not isinstance(key, str) or not key.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                    "Cannot build a session policy version with an empty, blank, or non-string configuration key."
                )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                "Cannot build a session policy version with a non-datetime created_at."
            )
