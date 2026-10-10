from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileValidationViolation:
    """
    Immutable description of a single way in which a consumer
    projection execution capability registry event subscription
    lifecycle policy profile, version, or version history failed
    validation.

    The violation is a value object only. It performs no
    validation, no accumulation, and no reporting. Validation and
    accumulation are the responsibility of a profile validator.

    Attributes:
        code: A short, stable, machine-readable identifier for the
            kind of violation
        message: A human-readable description of the violation
        profile_id: The identifier of the profile the violation was
            found on, or None if the violation was found on a
            standalone version or an unidentifiable profile
    """

    code: str

    message: str

    profile_id: (
        str | None
    )
