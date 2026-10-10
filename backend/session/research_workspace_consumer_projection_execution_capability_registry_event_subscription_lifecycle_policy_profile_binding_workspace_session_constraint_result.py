from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_constraint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionConstraintResult:
    """
    Immutable report of whether a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session schedule currently satisfies every
    enabled constraint assigned to it.

    The result is a value object only. It performs no evaluation.
    Evaluating constraints is the responsibility of a session
    scheduling constraint service.

    Attributes:
        satisfied: Whether every enabled constraint assigned to the
            schedule is currently satisfied
        violations: The identifiers of constraints found violated.
            Evaluation fails fast, so this holds at most one entry:
            the first enabled, assigned constraint, in deterministic
            order, that was not satisfied
    """

    satisfied: bool

    violations: tuple[
        str,
        ...,
    ]

    def __post_init__(self):
        if self.satisfied is None or not isinstance(self.satisfied, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                "Cannot build a session constraint result with a non-boolean satisfied."
            )

        if not isinstance(self.violations, tuple) or any(
            violation is None or not violation.strip() for violation in self.violations
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                "Cannot build a session constraint result with violations that is not a tuple of non-blank strings."
            )

        if self.satisfied and self.violations:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                "Cannot build a session constraint result that is satisfied but still names violations."
            )

        if not self.satisfied and not self.violations:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                "Cannot build an unsatisfied session constraint result without any violations."
            )
