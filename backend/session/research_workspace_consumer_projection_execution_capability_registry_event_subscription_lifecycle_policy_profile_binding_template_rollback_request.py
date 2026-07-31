from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackRequest:
    """
    Immutable request to restore a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding template to the state recorded by a specific deployment.

    The request is a value object only. It performs no lookup, no
    verification, and no rollback. Lookup, verification, and
    rollback are the responsibility of a rollback service.

    Attributes:
        template_id: The identifier of the template to roll back
        deployment_id: The identifier of the recorded deployment
            whose state should be restored
    """

    template_id: str

    deployment_id: str

    def __post_init__(self):
        if self.template_id is None or not self.template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                "Cannot build a rollback request with an empty or blank template ID."
            )

        if self.deployment_id is None or not self.deployment_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                "Cannot build a rollback request with an empty or blank deployment ID."
            )
