from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRelease:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding version's current position in its release lifecycle.

    The release is a value object only. It performs no transition
    logic. Transitions are the responsibility of a release service,
    which produces a new release record for every transition rather
    than mutating an existing one.

    Attributes:
        release_id: The release's unique identifier
        binding_id: The identifier of the binding the version
            belongs to
        version: The binding configuration version this release
            record describes
        status: The version's current release status
        released_at: When the version was first released, or None if
            it has never been released
    """

    release_id: str

    binding_id: str

    version: str

    status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus
    )

    released_at: (
        datetime | None
    )

    def __post_init__(self):
        if self.release_id is None or not self.release_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                "Cannot build a release with an empty or blank release ID."
            )

        if self.binding_id is None or not self.binding_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                "Cannot build a release with an empty or blank binding ID."
            )

        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                "Cannot build a release with an empty or blank version."
            )

        if not isinstance(
            self.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingReleaseError(
                "Cannot build a release with an invalid status."
            )
