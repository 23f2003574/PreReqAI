from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentConditionResult:
    """
    Immutable result containing the outcomes of a conditional assignment evaluation.

    Attributes:
        matched: True if an expression matched the runtime context successfully,
            False if it fell back to a normal assignment or None.
        selected_profile_id: The identifier of the resolved active profile,
            or None if no profile is active.
    """

    matched: bool

    selected_profile_id: str | None
