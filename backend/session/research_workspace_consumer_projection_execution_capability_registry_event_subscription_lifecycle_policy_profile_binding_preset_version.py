from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersion:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    preset's member binding templates and declared parameters at the
    moment it was published, so a deployment or instantiation can
    target a stable revision instead of the preset's mutable, current
    definition.

    The version is a value object only. It performs no publication,
    lookup, or rollback. Publication, lookup, and rollback are the
    responsibility of a binding preset version service.

    Attributes:
        version: The version's unique identifier
        template_ids: The identifiers of the preset's member binding
            templates at the moment this version was published, in
            stored order
        parameters: The preset's declared parameters at the moment
            this version was published, in declared order
        created_at: When this version was published
    """

    version: str

    template_ids: tuple

    parameters: tuple

    created_at: datetime

    def __post_init__(self):
        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                "Cannot build a preset version with an empty or blank version."
            )

        if self.template_ids is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                "Cannot build a preset version with None template IDs."
            )

        if self.parameters is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                "Cannot build a preset version with None parameters."
            )

        if self.created_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetVersionError(
                "Cannot build a preset version with a None created_at timestamp."
            )
