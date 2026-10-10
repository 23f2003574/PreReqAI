from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersion:
    """
    Immutable snapshot of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    template's member bindings and declared parameters at the moment
    it was published, so a deployment or instantiation can target a
    stable revision instead of the template's mutable, current
    definition.

    The version is a value object only. It performs no publication,
    lookup, or rollback. Publication, lookup, and rollback are the
    responsibility of a binding template version service.

    Attributes:
        version: The version's unique identifier
        binding_ids: The identifiers of the template's member
            bindings at the moment this version was published, in
            stored order
        parameters: The template's declared parameters at the moment
            this version was published, in declared order
        created_at: When this version was published
    """

    version: str

    binding_ids: tuple

    parameters: tuple

    created_at: datetime

    def __post_init__(self):
        if self.version is None or not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                "Cannot build a template version with an empty or blank version."
            )

        if self.binding_ids is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                "Cannot build a template version with None binding IDs."
            )

        if self.parameters is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                "Cannot build a template version with None parameters."
            )

        if self.created_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionError(
                "Cannot build a template version with a None created_at timestamp."
            )
