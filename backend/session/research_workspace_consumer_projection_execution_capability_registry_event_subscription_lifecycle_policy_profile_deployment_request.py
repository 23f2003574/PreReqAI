from dataclasses import (
    dataclass,
)

from typing import (
    Any,
    Mapping,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRequest:
    """
    Immutable request to deploy a consumer projection execution
    capability registry event subscription lifecycle policy profile
    version into a target runtime environment.

    The request is a value object only. It performs no resolution,
    no validation, and no deployment. Resolution, validation, and
    deployment are the responsibility of a deployment service.

    Attributes:
        profile_id: The identifier of the profile to deploy
        version: The published version to deploy, or None to
            resolve and deploy the profile's current version
        target_environment: The runtime environment to deploy into
        parameter_values: A caller-supplied mapping of parameter name
            to value, or None to fall back to the profile's defaults
    """

    profile_id: str

    version: (
        str
        | None
    )

    target_environment: str

    parameter_values: (
        Mapping[
            str,
            Any,
        ]
        | None
    )
