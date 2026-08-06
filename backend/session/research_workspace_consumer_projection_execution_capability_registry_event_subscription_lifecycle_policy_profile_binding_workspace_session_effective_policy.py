from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_inheritance import (
    VALID_SESSION_POLICY_INHERITANCE_FIELDS,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_inheritance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionEffectivePolicy:
    """
    Immutable, fully merged configuration of a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution session policy, after
    cascading every ancestor's configuration down through each
    inheritance link's overrides.

    The effective policy is a value object only. It performs no
    resolution. Resolving this merged configuration is the
    responsibility of a session policy inheritance service.

    Attributes:
        policy_id: The identifier of the policy this effective
            configuration was resolved for
        resolved_configuration: The fully merged configuration, with
            exactly one entry for each of "name", "max_runtime",
            "max_idle", "allow_restore", and "enabled"
    """

    policy_id: str

    resolved_configuration: dict

    def __post_init__(self):
        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                "Cannot build a session effective policy with an empty or blank policy ID."
            )

        if self.resolved_configuration is None or not isinstance(self.resolved_configuration, dict):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                "Cannot build a session effective policy with resolved_configuration that is not a dict."
            )

        if set(self.resolved_configuration.keys()) != set(VALID_SESSION_POLICY_INHERITANCE_FIELDS):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError(
                f"Cannot build a session effective policy: resolved_configuration must have exactly the keys "
                f"{VALID_SESSION_POLICY_INHERITANCE_FIELDS!r}."
            )
