from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_release_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_release_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRelease:
    """
    Immutable record of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    template version's position in its controlled release lifecycle.

    The release is a value object only. It performs no transition
    logic. Releasing and retiring are the responsibility of a
    release service, which produces a new release record for every
    transition rather than mutating an existing one.

    Attributes:
        release_id: The release record's unique identifier
        template_id: The identifier of the template the released
            version belongs to
        version: The template version this release record applies to
        status: The version's current stage in its release lifecycle
        released_at: When the version was first released, or None if
            it has never been released
    """

    release_id: str

    template_id: str

    version: str

    status: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus
    )

    released_at: (
        datetime | None
    )

    def __post_init__(self):
        if self.release_id is None or not self.release_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                "Cannot build a release with an empty or blank release ID."
            )

        if self.template_id is None or not self.template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                "Cannot build a release with an empty or blank template ID."
            )

        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                "Cannot build a release with an empty or blank version."
            )

        if not isinstance(
            self.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError(
                "Cannot build a release with an invalid status."
            )
