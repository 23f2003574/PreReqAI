from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetPreview:
    """
    Immutable preview of the consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace state that would result from applying a change set's
    staged operations.

    The preview is a value object only. It performs no computation
    and has no effect on the workspace's operational state. It is the
    responsibility of a binding workspace change set service to
    compute a preview without persisting it.

    Attributes:
        change_set_id: The identifier of the change set the preview
            was computed for
        workspace_id: The identifier of the workspace the preview
            concerns
        binding_ids: The workspace's resulting member binding IDs, had
            the change set been applied
        template_ids: The workspace's resulting member binding
            template IDs, had the change set been applied
        preset_ids: The workspace's resulting member binding preset
            IDs, had the change set been applied
        group_ids: The workspace's resulting member binding group IDs,
            had the change set been applied
    """

    change_set_id: str

    workspace_id: str

    binding_ids: tuple

    template_ids: tuple

    preset_ids: tuple

    group_ids: tuple
