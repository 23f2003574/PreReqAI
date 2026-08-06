from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_isolation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationResult:
    """
    Immutable outcome of validating a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session's resource access against its
    isolation policy.

    The result is a value object only. It performs no validation.
    Producing this outcome is the responsibility of a session
    isolation service.

    Attributes:
        isolated: Whether the session's current resource access is
            fully consistent with the isolation policy
        violations: The resource identifiers, if any, whose access
            conflicts with the isolation policy; always empty when
            isolated is True
    """

    isolated: bool

    violations: tuple[str, ...]

    def __post_init__(self):
        if self.isolated is None or not isinstance(self.isolated, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                "Cannot build a session isolation result with a non-boolean isolated."
            )

        if self.violations is None or not isinstance(self.violations, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                "Cannot build a session isolation result with violations that is not a tuple."
            )

        for violation in self.violations:
            if violation is None or not isinstance(violation, str) or not violation.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                    "Cannot build a session isolation result with an empty, blank, or non-string violation."
                )

        if self.isolated and self.violations:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                "Cannot build an isolated session isolation result with violations."
            )

        if not self.isolated and not self.violations:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                "Cannot build a non-isolated session isolation result without violations."
            )
