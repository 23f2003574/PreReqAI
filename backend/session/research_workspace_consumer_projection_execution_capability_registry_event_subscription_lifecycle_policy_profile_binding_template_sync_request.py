from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_sync_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncRequest:
    """
    Immutable request description for synchronizing a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding template's current definition,
    versions, and release metadata to a single target registry,
    deployment target, or runtime cache.

    The request is a value object only. It performs no lookup and no
    synchronization. Lookup and synchronization are the
    responsibility of a synchronization service.

    Attributes:
        template_id: The identifier of the template to synchronize
        operation: The sync operation, either "register" to push the
            template's current state to the target, or "remove" to
            remove the template's state from the target
        target: The identifier of the target registry, deployment
            target, or runtime cache to synchronize
    """

    template_id: str

    operation: str

    target: str

    def __post_init__(self):
        if self.template_id is None or not self.template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError(
                "Cannot build a sync request with an empty or blank template ID."
            )

        if self.operation is None or not self.operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError(
                "Cannot build a sync request with an empty or blank operation."
            )

        if self.operation not in ("register", "remove"):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError(
                f"Invalid sync request operation {self.operation!r}. Must be 'register' or 'remove'."
            )

        if self.target is None or not self.target.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateSyncError(
                "Cannot build a sync request with an empty or blank target."
            )
