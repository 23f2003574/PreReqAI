from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_change_set_rebase_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebaseStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_rebase_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebase:
    """
    Immutable record of a single attempt to rebase a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace change set onto a
    newer workspace revision.

    The rebase record is a value object only. It performs no
    rebasing. Rebasing a change set, and producing this record, is
    the responsibility of a binding workspace rebase service.

    Attributes:
        rebase_id: The rebase attempt's unique identifier
        change_set_id: The identifier of the change set that was
            rebased
        source_revision: The revision the change set was rebased
            from, or None if it had never previously been rebased
        target_revision: The revision the change set was rebased onto
        status: The rebase attempt's outcome
    """

    rebase_id: str

    change_set_id: str

    source_revision: str | None

    target_revision: str

    status: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebaseStatus

    def __post_init__(self):
        if self.rebase_id is None or not self.rebase_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                "Cannot build a change set rebase with an empty or blank rebase ID."
            )

        if self.change_set_id is None or not self.change_set_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                "Cannot build a change set rebase with an empty or blank change set ID."
            )

        if self.source_revision is not None and not self.source_revision.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                "Cannot build a change set rebase with a blank source revision; omit it entirely instead."
            )

        if self.target_revision is None or not self.target_revision.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                "Cannot build a change set rebase with an empty or blank target revision."
            )

        if not isinstance(
            self.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebaseStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRebaseError(
                "Cannot build a change set rebase: status must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceChangeSetRebaseStatus."
            )
