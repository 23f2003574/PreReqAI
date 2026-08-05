from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_cleanup_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupResult:
    """
    Immutable tally of a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace session cleanup pass.

    The result is a value object only. It performs no scanning,
    archiving, or retirement. Producing this tally is the
    responsibility of a session cleanup service.

    Attributes:
        scanned: How many sessions were examined
        archived: How many of the scanned sessions were archived
        deleted: How many of the scanned sessions were retired
    """

    scanned: int

    archived: int

    deleted: int

    def __post_init__(self):
        for value, label in (
            (self.scanned, "scanned"),
            (self.archived, "archived"),
            (self.deleted, "deleted"),
        ):
            if value is None or isinstance(value, bool) or not isinstance(value, int):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError(
                    f"Cannot build a session cleanup result with a non-integer {label} count."
                )

            if value < 0:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError(
                    f"Cannot build a session cleanup result with a negative {label} count."
                )

        if self.archived > self.scanned or self.deleted > self.scanned:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError(
                "Cannot build a session cleanup result where archived or deleted exceeds scanned."
            )
