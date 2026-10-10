from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_metrics import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetrics,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_metrics_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthReport:
    """
    Immutable report summarizing the health of every branch on a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace at the
    moment it was generated.

    The report is a value object only. It performs no computation.
    Generating a report is the responsibility of a binding workspace
    branch metrics service.

    Attributes:
        generated_at: When the report was generated
        branch_metrics: The metrics for every branch on the
            workspace, in the order the branches were created
        recommendations: Human-readable, actionable observations
            derived from branch_metrics; empty if nothing warranted
            flagging
    """

    generated_at: datetime

    branch_metrics: tuple

    recommendations: tuple

    def __post_init__(self):
        if self.generated_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                "Cannot build a branch health report with a None generated_at."
            )

        if self.branch_metrics is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                "Cannot build a branch health report with None branch_metrics."
            )

        for metrics in self.branch_metrics:
            if not isinstance(
                metrics,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetrics,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                    "Cannot build a branch health report: every entry in branch_metrics must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetrics."
                )

        if self.recommendations is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                "Cannot build a branch health report with None recommendations."
            )

        for recommendation in self.recommendations:
            if recommendation is None or not recommendation.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchMetricsError(
                    "Cannot build a branch health report with an empty or blank recommendation."
                )
