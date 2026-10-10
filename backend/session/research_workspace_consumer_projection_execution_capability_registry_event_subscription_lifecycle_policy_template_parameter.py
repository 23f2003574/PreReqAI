from dataclasses import (
    dataclass,
)

from typing import Any


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateParameter:
    """
    Immutable description of a single configurable parameter a
    consumer projection execution capability registry event
    subscription lifecycle policy template exposes.

    The parameter is a value object only. It performs no
    validation, no defaulting, and no application. Validation,
    defaulting, and application are the responsibility of a
    parameterization service.

    A default_value of None is treated as "no default supplied";
    a parameter with no default must either be optional or have a
    value supplied at application time.

    Attributes:
        name: The parameter's unique name within its parameter set
        type: The Python type a supplied value must be an instance
            of, or None to accept any type
        required: Whether a value must be present, either supplied
            or defaulted, for this parameter
        default_value: The value used when the parameter is omitted,
            or None if the parameter has no default
    """

    name: str

    type: type | None

    required: bool

    default_value: Any
