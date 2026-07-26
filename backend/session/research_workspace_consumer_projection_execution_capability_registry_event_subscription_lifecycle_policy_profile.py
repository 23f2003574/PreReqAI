from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfile:
    """
    Immutable, named grouping of consumer projection execution
    capability registry event subscription lifecycle policy
    identifiers, addressed by a profile identifier.

    The profile is a value object only. It performs no
    registration, no lookup, and no resolution of the policies its
    identifiers refer to. Registration and lookup are the
    responsibility of a profile service; policy resolution is the
    responsibility of a policy catalog or registry.

    Attributes:
        profile_id: The profile's unique identifier
        profile_name: The profile's human-readable name
        description: A human-readable description of the profile
        policy_identifiers: An immutable, order-preserving tuple of
            the unique lifecycle policy identifiers grouped under
            this profile
    """

    profile_id: str

    profile_name: str

    description: str

    policy_identifiers: tuple[
        str,
        ...,
    ]

    def __post_init__(self):

        if (

            self.profile_id is None

            or not self.profile_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError(
                    "Cannot build a profile with an empty or blank profile ID."
                )
            )

        if (

            self.profile_name is None

            or not self.profile_name.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError(
                    "Cannot build a profile with an empty or blank profile name."
                )
            )

        if len(
            set(
                self.policy_identifiers
            )
        ) != len(
            self.policy_identifiers
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileError(
                    "Cannot build a profile with duplicate policy identifiers."
                )
            )
