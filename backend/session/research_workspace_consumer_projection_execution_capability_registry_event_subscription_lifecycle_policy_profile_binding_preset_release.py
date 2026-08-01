from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRelease:
    """
    Immutable record of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    preset version's position in its controlled release lifecycle.

    The release is a value object only. It performs no transition
    logic. Releasing and retiring are the responsibility of a
    release service, which produces a new release record for every
    transition rather than mutating an existing one.

    Attributes:
        release_id: The release record's unique identifier
        preset_id: The identifier of the preset the released version
            belongs to
        version: The preset version this release record applies to
        status: The version's current stage in its release lifecycle
        released_at: When the version was first released, or None if
            it has never been released
    """

    release_id: str

    preset_id: str

    version: str

    status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus
    )

    released_at: (
        datetime | None
    )

    def __post_init__(self):
        if self.release_id is None or not self.release_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                "Cannot build a release with an empty or blank release ID."
            )

        if self.preset_id is None or not self.preset_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                "Cannot build a release with an empty or blank preset ID."
            )

        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                "Cannot build a release with an empty or blank version."
            )

        if not isinstance(
            self.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetReleaseError(
                "Cannot build a release with an invalid status."
            )
