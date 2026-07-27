from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentValidationViolation:
    """
    Immutable description of a single way in which a consumer
    projection execution capability registry event subscription
    lifecycle policy profile assignment failed validation.

    The violation is a value object only. It performs no validation,
    no accumulation, and no reporting. Validation and accumulation
    are the responsibility of an assignment validator.

    Attributes:
        code: A short, stable, machine-readable identifier for the
            kind of violation
        message: A human-readable description of the violation
        target_id: The identifier of the target the violation was
            found on, or None if the violation was found on a subject
            with no identifiable target
    """

    code: str

    message: str

    target_id: (
        str | None
    )
