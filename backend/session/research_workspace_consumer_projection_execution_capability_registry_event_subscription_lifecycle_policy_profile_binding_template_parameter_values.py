from dataclasses import (
    dataclass,
)

from typing import (
    Any,
    Mapping,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterValues:
    """
    Immutable, order-preserving set of parameter values for a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding template's
    parameter set.

    The values are a value object only. They perform no validation,
    no defaulting, and no application. Validation, defaulting, and
    application are the responsibility of a parameterization service.

    Attributes:
        values: An immutable, order-preserving mapping of parameter
            name to supplied or defaulted value
    """

    values: Mapping[
        str,
        Any,
    ]
