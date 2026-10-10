from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchHealthStatus(
    str,
    Enum,
):
    """
    Canonical health classifications a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace branch's health score can fall into.

    This enum only names the possible classifications. It performs no
    scoring; a workspace branch metrics service is responsible for
    computing a branch's health score and classifying it.
    """

    HEALTHY = "healthy"

    AT_RISK = "at_risk"

    CRITICAL = "critical"
