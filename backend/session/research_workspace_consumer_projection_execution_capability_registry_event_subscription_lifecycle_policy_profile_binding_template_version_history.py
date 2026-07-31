from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionHistory:
    """
    Immutable, chronologically ordered collection of every version
    ever published for a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    template, together with a pointer to its current version.

    The history is a value object only. It performs no publication,
    no lookup, and no rollback. Publication, lookup, and rollback are
    the responsibility of a binding template version service.

    Attributes:
        template_id: The identifier of the template this history
            belongs to
        current_version: The version identifier currently in effect
            for the template
        versions: An immutable, order-preserving tuple of every
            version ever published for the template, in the order
            they were published
    """

    template_id: str

    current_version: str

    versions: tuple[
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion,
        ...,
    ]

    def __post_init__(self):
        if self.template_id is None or not self.template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                "Cannot build a template version history with an empty or blank template ID."
            )

        if self.current_version is None or not self.current_version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                "Cannot build a template version history with an empty or blank current version."
            )

        if not self.versions:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                "Cannot build a template version history with no versions."
            )

        if not any(version.version == self.current_version for version in self.versions):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                f"Cannot build a template version history: current version {self.current_version!r} is not among its versions."
            )
