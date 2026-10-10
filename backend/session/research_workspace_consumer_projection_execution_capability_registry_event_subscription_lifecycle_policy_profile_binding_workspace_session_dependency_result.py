from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_dependency_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionDependencyResult:
    """
    Immutable report of whether a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session schedule's prerequisites have all
    completed successfully.

    The result is a value object only. It performs no completion
    checking. Validating a schedule's dependencies is the
    responsibility of a session schedule dependency service.

    Attributes:
        satisfied: Whether every prerequisite session the schedule
            depends on has completed successfully
        blocking_sessions: The identifiers of prerequisite sessions
            that have not yet completed successfully, in the order
            their dependencies were added; empty when satisfied is
            True
    """

    satisfied: bool

    blocking_sessions: tuple[
        str,
        ...,
    ]

    def __post_init__(self):
        if self.satisfied is None or not isinstance(self.satisfied, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                "Cannot build a session dependency result with a non-boolean satisfied."
            )

        if not isinstance(self.blocking_sessions, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                "Cannot build a session dependency result with a non-tuple blocking_sessions."
            )

        if any(session_id is None or not session_id.strip() for session_id in self.blocking_sessions):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                "Cannot build a session dependency result with an empty or blank blocking session ID."
            )

        if self.satisfied and self.blocking_sessions:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                "Cannot build a session dependency result that is satisfied but still names blocking sessions."
            )

        if not self.satisfied and not self.blocking_sessions:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                "Cannot build an unsatisfied session dependency result without any blocking sessions."
            )
