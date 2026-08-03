from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_merge_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetMerge:
    """
    Immutable record of a successful merge of multiple consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace change sets into a
    single, consolidated change set.

    The merge record is a value object only. It performs no merging.
    Merging change sets, and producing this record, is the
    responsibility of a binding workspace merge service.

    Attributes:
        merge_id: The merge's unique identifier
        workspace_id: The identifier of the workspace every source
            and the merged change set belong to
        source_change_set_ids: The identifiers of the change sets that
            were merged, in the order they were merged
        merged_change_set_id: The identifier of the newly created,
            consolidated change set holding every source operation
        merged_at: When the merge was performed
    """

    merge_id: str

    workspace_id: str

    source_change_set_ids: tuple

    merged_change_set_id: str

    merged_at: datetime

    def __post_init__(self):
        if self.merge_id is None or not self.merge_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                "Cannot build a change set merge with an empty or blank merge ID."
            )

        if self.workspace_id is None or not self.workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                "Cannot build a change set merge with an empty or blank workspace ID."
            )

        if not self.source_change_set_ids:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                "Cannot build a change set merge with no source change set IDs."
            )

        for source_change_set_id in self.source_change_set_ids:
            if source_change_set_id is None or not source_change_set_id.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                    "Cannot build a change set merge with an empty or blank source change set ID."
                )

        if len(set(self.source_change_set_ids)) != len(self.source_change_set_ids):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                "Cannot build a change set merge with duplicate source change set IDs."
            )

        if self.merged_change_set_id is None or not self.merged_change_set_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                "Cannot build a change set merge with an empty or blank merged change set ID."
            )

        if self.merged_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceMergeError(
                "Cannot build a change set merge with a None merged_at."
            )
