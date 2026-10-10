from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentOverrideResult:
    """
    Immutable result containing the resolved effective profile and a flag showing
    if an override was applied.

    Attributes:
        effective_profile_id: The identifier of the resolved active profile (from override or normal assignment),
            or None if no profile is active.
        override_applied: True if the resolved profile came from an override, False if it was
            from normal assignment fallback.
    """

    effective_profile_id: str | None

    override_applied: bool
