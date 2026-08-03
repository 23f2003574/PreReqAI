from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_metrics_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetrics:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace branch's health indicators at the moment they were
    computed.

    The metrics are a value object only. They perform no computation.
    Computing metrics for a branch is the responsibility of a binding
    workspace branch metrics service.

    Attributes:
        branch_id: The identifier of the branch the metrics concern
        change_set_count: The number of open change sets currently
            staged against the branch's workspace
        conflict_count: The number of distinct unresolved conflicts
            across those open change sets
        days_since_sync: The number of whole days since the branch was
            last successfully synchronized with its workspace's latest
            revision, or since it was created if it has never been
            synchronized
        health_score: A 0-100 score summarizing the branch's health;
            higher is healthier
    """

    branch_id: str

    change_set_count: int

    conflict_count: int

    days_since_sync: int

    health_score: int

    def __post_init__(self):
        if self.branch_id is None or not self.branch_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                "Cannot build branch metrics with an empty or blank branch ID."
            )

        for field_name in ("change_set_count", "conflict_count", "days_since_sync"):
            value = getattr(self, field_name)

            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                    f"Cannot build branch metrics: {field_name} must be a non-negative int."
                )

        if not isinstance(self.health_score, int) or isinstance(self.health_score, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                "Cannot build branch metrics: health_score must be an int."
            )

        if not (0 <= self.health_score <= 100):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                "Cannot build branch metrics with a health_score outside the range 0-100."
            )
