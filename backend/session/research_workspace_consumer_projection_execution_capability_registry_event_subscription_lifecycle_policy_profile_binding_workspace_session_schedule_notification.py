from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_notification_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleNotification:
    """
    Immutable notification announcing that a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace session schedule reached a lifecycle
    event, so interested consumers can react without being coupled to
    the scheduler itself.

    The notification is a value object only. It performs no
    delivery. Publishing notifications and delivering them to
    recipients is the responsibility of a session scheduling
    notification service.

    Attributes:
        notification_id: The notification's unique identifier
        schedule_id: The identifier of the schedule this notification
            concerns
        event: The lifecycle event that was reached, such as
            "created", "dispatched", or "cancelled"
        recipients: The identifiers of every consumer this
            notification is meant for
        created_at: When this notification was published
    """

    notification_id: str

    schedule_id: str

    event: str

    recipients: tuple[
        str,
        ...,
    ]

    created_at: datetime

    def __post_init__(self):
        if self.notification_id is None or not self.notification_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a session schedule notification with an empty or blank notification ID."
            )

        if self.schedule_id is None or not self.schedule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a session schedule notification with an empty or blank schedule ID."
            )

        if self.event is None or not self.event.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a session schedule notification with an empty or blank event."
            )

        if (
            not isinstance(self.recipients, tuple)
            or not self.recipients
            or any(
                recipient is None or not isinstance(recipient, str) or not recipient.strip()
                for recipient in self.recipients
            )
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a session schedule notification without a non-empty tuple of non-blank recipients."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime) or self.created_at.utcoffset() is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a session schedule notification with a non-timezone-aware created_at."
            )
