from dataclasses import (
    dataclass,
)

from datetime import datetime

from typing import Optional

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_notification_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionNotificationDelivery:
    """
    Immutable outcome of a single attempt to deliver a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace session schedule
    notification to its recipients.

    The delivery is a value object only. It performs no delivery
    itself. Attempting and retrying deliveries is the responsibility
    of a session scheduling notification service.

    Attributes:
        notification_id: The identifier of the notification this
            delivery attempt concerns
        delivered: Whether this attempt succeeded
        delivered_at: When this attempt succeeded, or None when
            delivered is False
    """

    notification_id: str

    delivered: bool

    delivered_at: Optional[datetime]

    def __post_init__(self):
        if self.notification_id is None or not self.notification_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a session notification delivery with an empty or blank notification ID."
            )

        if self.delivered is None or not isinstance(self.delivered, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a session notification delivery with a non-boolean delivered."
            )

        if self.delivered_at is not None and (
            not isinstance(self.delivered_at, datetime) or self.delivered_at.utcoffset() is None
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a session notification delivery with a non-timezone-aware delivered_at."
            )

        if self.delivered and self.delivered_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a delivered session notification delivery without a delivered_at."
            )

        if not self.delivered and self.delivered_at is not None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a non-delivered session notification delivery with a delivered_at."
            )
