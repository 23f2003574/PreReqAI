from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchProtectionResult:
    """
    Immutable result of evaluating an attempted operation against a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace branch's
    protection rules.

    Attributes:
        permitted: True if the operation does not violate any active
            protection rule
        violations: A human-readable description of every protection
            rule the operation violated; empty if permitted is True
    """

    permitted: bool

    violations: tuple
