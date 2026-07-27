from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_resolution_result_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResultError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_resolution_source import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResult:
    """
    Immutable outcome produced after resolving the active profile
    assignment for a target identifier.

    The result is a value object only. It performs no resolution
    and no lookup. Resolution and lookup are the responsibility of
    an assignment resolver.

    Attributes:
        target_id: The identifier of the target for which resolution
            was attempted
        assignment: The active assignment that was resolved, or None
            if resolution failed
        resolved: Whether an active assignment was resolved
        resolution_source: Which source satisfied the resolution, or
            None if resolution failed
    """

    target_id: str

    assignment: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment
        | None
    )

    resolved: bool

    resolution_source: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource
        | None
    )

    def __post_init__(self):

        if self.resolved:

            if self.assignment is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResultError(
                        "Cannot build a resolution result: a resolved "
                        "result must carry an assignment."
                    )
                )

            if not isinstance(

                self.resolution_source,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionSource,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResultError(
                        "Cannot build a resolution result: a resolved "
                        "result must carry a known resolution source."
                    )
                )

        else:

            if self.assignment is not None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResultError(
                        "Cannot build a resolution result: an unresolved "
                        "result must not carry an assignment."
                    )
                )

            if self.resolution_source is not None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResolutionResultError(
                        "Cannot build a resolution result: an unresolved "
                        "result must not carry a resolution source."
                    )
                )
