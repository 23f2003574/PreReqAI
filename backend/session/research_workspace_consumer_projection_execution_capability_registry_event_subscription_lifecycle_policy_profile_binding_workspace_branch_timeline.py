from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_audit_event import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditEvent,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTimeline:
    """
    Immutable, chronologically ordered activity timeline for a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace branch.

    The timeline is a value object only. It performs no recording and
    has no effect on the branch's operational state.

    Attributes:
        branch_id: The identifier of the branch the timeline concerns
        events: The branch's audit events, in chronological order
    """

    branch_id: str

    events: tuple

    def __post_init__(self):
        if self.branch_id is None or not self.branch_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot build a branch timeline with an empty or blank branch ID."
            )

        if self.events is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot build a branch timeline with None events."
            )

        for event in self.events:
            if not isinstance(
                event,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditEvent,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                    "Cannot build a branch timeline: every event must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditEvent."
                )

            if event.branch_id != self.branch_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                    f"Cannot build a branch timeline: event branch ID {event.branch_id!r} does not match "
                    f"timeline branch ID {self.branch_id!r}."
                )
