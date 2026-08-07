from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingReplayResult:
    """
    Immutable outcome of deterministically replaying every consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace session scheduling
    audit event recorded for a schedule.

    The result is a value object only. It performs no replay.
    Replaying a schedule's recorded decisions is the responsibility
    of a session scheduling audit service.

    Attributes:
        schedule_id: The identifier of the schedule this result
            concerns
        replayed: Whether at least one audit event was found to
            replay
        decision_trace: The event_type of every audit event recorded
            for the schedule, in the chronological order they were
            originally made; empty when replayed is False
    """

    schedule_id: str

    replayed: bool

    decision_trace: tuple[
        str,
        ...,
    ]

    def __post_init__(self):
        if self.schedule_id is None or not self.schedule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot build a session scheduling replay result with an empty or blank schedule ID."
            )

        if self.replayed is None or not isinstance(self.replayed, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot build a session scheduling replay result with a non-boolean replayed."
            )

        if not isinstance(self.decision_trace, tuple) or any(
            step is None or not isinstance(step, str) or not step.strip() for step in self.decision_trace
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot build a session scheduling replay result with a decision_trace that is not a tuple of "
                "non-blank strings."
            )

        if self.replayed and not self.decision_trace:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot build a replayed session scheduling replay result with an empty decision_trace."
            )

        if not self.replayed and self.decision_trace:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAuditError(
                "Cannot build a non-replayed session scheduling replay result with a non-empty decision_trace."
            )
