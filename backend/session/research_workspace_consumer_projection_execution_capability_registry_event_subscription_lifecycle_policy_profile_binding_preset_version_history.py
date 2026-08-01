from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionHistory:
    """
    Immutable, chronologically ordered collection of every version
    ever published for a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    preset, together with a pointer to its current version.

    The history is a value object only. It performs no publication,
    no lookup, and no rollback. Publication, lookup, and rollback are
    the responsibility of a binding preset version service.

    Attributes:
        preset_id: The identifier of the preset this history belongs
            to
        current_version: The version identifier currently in effect
            for the preset
        versions: An immutable, order-preserving tuple of every
            version ever published for the preset, in the order they
            were published
    """

    preset_id: str

    current_version: str

    versions: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion,
        ...,
    ]

    def __post_init__(self):
        if self.preset_id is None or not self.preset_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                "Cannot build a preset version history with an empty or blank preset ID."
            )

        if self.current_version is None or not self.current_version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                "Cannot build a preset version history with an empty or blank current version."
            )

        if not self.versions:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                "Cannot build a preset version history with no versions."
            )

        if not any(version.version == self.current_version for version in self.versions):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                f"Cannot build a preset version history: current version {self.current_version!r} is not among its versions."
            )
