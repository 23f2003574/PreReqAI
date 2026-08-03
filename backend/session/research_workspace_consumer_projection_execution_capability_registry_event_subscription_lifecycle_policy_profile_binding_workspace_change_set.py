from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_operation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSet:
    """
    Immutable record of a staged batch of edits to a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace, allowing multiple
    changes to be reviewed together and committed atomically instead
    of modifying the workspace directly.

    The change set is a value object only. It performs no staging,
    preview, application, or discarding. Those are the responsibility
    of a binding workspace change set service, which produces a new
    change set record for every change rather than mutating an
    existing one.

    Attributes:
        change_set_id: The change set's unique identifier
        workspace_id: The identifier of the workspace the change set
            targets
        name: The change set's human-readable name
        description: A human-readable description of the change set
        operations: The change set's staged operations, in the order
            they were added
        status: The change set's current lifecycle state
        created_at: When the change set was created
    """

    change_set_id: str

    workspace_id: str

    name: str

    description: str | None

    operations: tuple

    status: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus

    created_at: datetime

    def __post_init__(self):
        if self.change_set_id is None or not self.change_set_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change set with an empty or blank change set ID."
            )

        if self.workspace_id is None or not self.workspace_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change set with an empty or blank workspace ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change set with an empty or blank name."
            )

        if self.operations is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change set with None operations."
            )

        for operation in self.operations:
            if not isinstance(
                operation,
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation,
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                    "Cannot build a change set: every operation must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeOperation."
                )

        operation_ids = [operation.operation_id for operation in self.operations]

        if len(set(operation_ids)) != len(operation_ids):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change set with duplicate operation IDs."
            )

        if not isinstance(
            self.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change set: status must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetStatus."
            )

        if self.created_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetError(
                "Cannot build a change set with a None created_at."
            )
