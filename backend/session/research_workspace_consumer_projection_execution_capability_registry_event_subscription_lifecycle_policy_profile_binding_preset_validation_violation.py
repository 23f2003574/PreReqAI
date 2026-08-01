from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetValidationViolation:
    """
    Immutable description of a single way in which a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding preset failed validation.

    The violation is a value object only. It performs no validation,
    no accumulation, and no reporting. Validation and accumulation
    are the responsibility of a binding preset validator.

    Attributes:
        code: A short, stable, machine-readable identifier for the
            kind of violation
        message: A human-readable description of the violation
        preset_id: The identifier of the preset the violation was
            found on, or None if the violation was found on a subject
            with no identifiable preset
    """

    code: str

    message: str

    preset_id: (
        str | None
    )
