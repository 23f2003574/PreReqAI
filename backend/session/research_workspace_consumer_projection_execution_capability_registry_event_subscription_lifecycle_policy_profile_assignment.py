from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment:
    """
    Immutable record of a single assignment linking a registered
    lifecycle policy profile to a capability, subscription, or
    execution context target.

    The assignment is a value object only. It performs no assignment
    logic. Assignment and unassignment are the responsibility of an
    assignment service, which produces a new assignment record for
    every assignment rather than mutating an existing one.

    Attributes:
        assignment_id: The assignment's unique identifier
        target_id: The identifier of the capability, subscription,
            or execution context the profile is assigned to
        profile_id: The identifier of the assigned profile
        assigned_at: When the assignment was recorded
    """

    assignment_id: str

    target_id: str

    profile_id: str

    assigned_at: datetime

    def __post_init__(self):

        if (

            self.assignment_id is None

            or not self.assignment_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError(
                    "Cannot build an assignment with an empty or blank "
                    "assignment ID."
                )
            )

        if (

            self.target_id is None

            or not self.target_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError(
                    "Cannot build an assignment with an empty or blank "
                    "target ID."
                )
            )

        if (

            self.profile_id is None

            or not self.profile_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError(
                    "Cannot build an assignment with an empty or blank "
                    "profile ID."
                )
            )
