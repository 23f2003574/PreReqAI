from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_dependency_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependency:
    """
    Immutable requirement that a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session schedule may only execute once a named
    prerequisite execution session has completed successfully.

    The dependency is a value object only. It performs no cycle
    detection or completion checking. Adding, removing, and validating
    dependencies is the responsibility of a session schedule
    dependency service.

    Attributes:
        dependency_id: The dependency's unique identifier
        schedule_id: The identifier of the schedule this dependency
            constrains
        prerequisite_session_id: The identifier of the execution
            session that must complete successfully before
            schedule_id may execute
    """

    dependency_id: str

    schedule_id: str

    prerequisite_session_id: str

    def __post_init__(self):
        if self.dependency_id is None or not self.dependency_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                "Cannot build a session schedule dependency with an empty or blank dependency ID."
            )

        if self.schedule_id is None or not self.schedule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                "Cannot build a session schedule dependency with an empty or blank schedule ID."
            )

        if self.prerequisite_session_id is None or not self.prerequisite_session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                "Cannot build a session schedule dependency with an empty or blank prerequisite session ID."
            )
