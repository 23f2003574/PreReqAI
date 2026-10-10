from dataclasses import (
    dataclass,
)

from typing import (
    Any,
    Mapping,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileInstance:
    """
    Immutable, executable instance of a consumer projection
    execution capability registry event subscription lifecycle
    policy profile, created from a registered profile definition at
    a specific published version.

    The instance is a value object only. It performs no resolution,
    no validation, and no instantiation. Resolution, validation, and
    instantiation are the responsibility of a profile instantiation
    service.

    Attributes:
        profile_id: The identifier of the profile this instance was
            instantiated from
        version: The identifier of the published version this
            instance was instantiated from, or None if the instance
            was parameterized directly from a profile without
            reference to a specific published version
        policy_identifiers: An immutable, order-preserving tuple of
            the lifecycle policy identifiers grouped under the
            instantiated version
        parameter_values: An immutable, order-preserving mapping of
            parameter name to supplied or defaulted value
    """

    profile_id: str

    version: (
        str
        | None
    )

    policy_identifiers: tuple[
        str,
        ...,
    ]

    parameter_values: Mapping[
        str,
        Any,
    ]
