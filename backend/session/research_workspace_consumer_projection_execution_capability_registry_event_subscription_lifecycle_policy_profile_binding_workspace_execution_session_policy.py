from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_policy_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy:
    """
    Immutable, reusable configuration describing how long a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session is
    allowed to run and sit idle, and whether it may be restored, kept
    independent of any single session instance.

    The policy is a value object only. It performs no enforcement.
    Registering, assigning, and validating policies against sessions
    are the responsibility of a session policy service.

    Attributes:
        policy_id: The policy's unique identifier
        name: A human-readable label for the policy
        max_runtime: How long, in seconds, a session governed by this
            policy is allowed to run before it is no longer compliant
        max_idle: How long, in seconds, a session governed by this
            policy is allowed to sit idle before it is no longer
            compliant
        allow_restore: Whether a session governed by this policy may
            be restored after being interrupted
        enabled: Whether this policy may currently be assigned to a
            session
    """

    policy_id: str

    name: str

    max_runtime: float

    max_idle: float

    allow_restore: bool

    enabled: bool

    def __post_init__(self):
        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                "Cannot build a session policy with an empty or blank policy ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                "Cannot build a session policy with an empty or blank name."
            )

        for value, label in (
            (self.max_runtime, "max_runtime"),
            (self.max_idle, "max_idle"),
        ):
            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                    f"Invalid session policy {label} {value!r}; {label} must be a positive number of seconds."
                )

        if self.allow_restore is None or not isinstance(self.allow_restore, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                "Cannot build a session policy with a non-boolean allow_restore."
            )

        if self.enabled is None or not isinstance(self.enabled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyError(
                "Cannot build a session policy with a non-boolean enabled."
            )
