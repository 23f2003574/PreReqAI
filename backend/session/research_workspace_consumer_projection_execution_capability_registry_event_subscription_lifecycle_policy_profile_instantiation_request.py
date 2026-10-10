from dataclasses import (
    dataclass,
)

from typing import (
    Any,
    Mapping,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstantiationRequest:
    """
    Immutable request to instantiate a new consumer projection
    execution capability registry event subscription lifecycle
    policy profile instance from a registered profile definition.

    The request is a value object only. It performs no resolution,
    no validation, and no instantiation. Resolution, validation, and
    instantiation are the responsibility of a profile instantiation
    service.

    Attributes:
        profile_id: The identifier of the profile to instantiate
            from
        version: The identifier of the published version to
            instantiate from
        parameter_values: A caller-supplied mapping of parameter name
            to value, or None to fall back to the profile's defaults
    """

    profile_id: str

    version: str

    parameter_values: (
        Mapping[
            str,
            Any,
        ]
        | None
    )
