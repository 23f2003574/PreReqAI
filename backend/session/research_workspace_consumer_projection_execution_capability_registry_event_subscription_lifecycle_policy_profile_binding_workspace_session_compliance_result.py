from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_compliance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceResult:
    """
    Immutable outcome of evaluating a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session against every currently
    enabled compliance rule.

    The result is a value object only. It performs no evaluation.
    Producing this outcome is the responsibility of a session
    compliance service.

    Attributes:
        compliant: Whether the session violated no enabled rule
        violations: The rule IDs of every enabled rule the session
            violated; always empty when compliant is True
    """

    compliant: bool

    violations: tuple[str, ...]

    def __post_init__(self):
        if self.compliant is None or not isinstance(self.compliant, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                "Cannot build a session compliance result with a non-boolean compliant."
            )

        if self.violations is None or not isinstance(self.violations, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                "Cannot build a session compliance result with violations that is not a tuple."
            )

        for violation in self.violations:
            if violation is None or not isinstance(violation, str) or not violation.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                    "Cannot build a session compliance result with an empty, blank, or non-string violation."
                )

        if self.compliant and self.violations:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                "Cannot build a compliant session compliance result with violations."
            )

        if not self.compliant and not self.violations:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                "Cannot build a non-compliant session compliance result without violations."
            )
