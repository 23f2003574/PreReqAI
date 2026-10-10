from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_notification_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_notification import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleNotification,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_notification_delivery import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionNotificationDelivery,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationService:
    """
    Notifies a fixed set of interested consumers whenever a consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace session schedule
    reaches a lifecycle event, without coupling those consumers to
    the scheduler itself.

    The service's responsibility is publishing and delivering
    notifications, not detecting lifecycle events. It does NOT
    observe the scheduler on its own; a caller, such as the session
    scheduler, is expected to call publish() as each lifecycle event
    occurs.

    Behavior:
    - At most one notification may ever be published per
      (schedule_id, event) pair; publishing the same pair again is
      rejected, so recipients are never notified twice for the same
      event
    - Every delivery attempt is kept, never overwritten, so a
      notification's full delivery history survives every retry()
    - retry() only re-attempts a notification that has already had at
      least one delivery attempt and whose most recent attempt did
      not succeed
    - pending() reports every notification whose most recent delivery
      attempt, if any, has not succeeded

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, recipients: tuple, delivery_handler=None):
        """
        Args:
            recipients: The fixed set of consumer identifiers every
                published notification is addressed to
            delivery_handler: An optional callable accepting a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleNotification
                and returning whether delivery succeeded. When
                omitted, every delivery attempt succeeds

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError:
                If recipients is not a non-empty tuple of unique,
                non-blank strings, or delivery_handler is given but
                not callable
        """

        if (
            not isinstance(recipients, tuple)
            or not recipients
            or any(recipient is None or not isinstance(recipient, str) or not recipient.strip() for recipient in recipients)
            or len(set(recipients)) != len(recipients)
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a session scheduling notification service with recipients that is not a "
                "non-empty tuple of unique, non-blank strings."
            )

        if delivery_handler is not None and not callable(delivery_handler):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                "Cannot build a session scheduling notification service with a non-callable delivery_handler."
            )

        self._recipients = recipients
        self._delivery_handler = delivery_handler
        self._notifications = {}
        self._notification_ids_by_schedule_id = {}
        self._published_keys = set()
        self._deliveries_by_notification_id = {}
        self._lock = RLock()

    def publish(self, schedule_id: str, event: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleNotification:
        """
        Publish a notification for a schedule reaching a lifecycle
        event.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError:
                If schedule_id or event is None or blank, or this
                (schedule_id, event) pair was already published
        """

        self._validate_id(schedule_id, "schedule ID")
        self._validate_id(event, "event")

        with self._lock:
            key = (schedule_id, event)

            if key in self._published_keys:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                    f"A notification for schedule ID {schedule_id!r} and event {event!r} was already published."
                )

            notification = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleNotification(
                notification_id=str(uuid4()),
                schedule_id=schedule_id,
                event=event,
                recipients=self._recipients,
                created_at=datetime.now(timezone.utc),
            )

            self._notifications[notification.notification_id] = notification
            self._notification_ids_by_schedule_id.setdefault(schedule_id, []).append(notification.notification_id)
            self._published_keys.add(key)

            return notification

    def deliver(self, notification_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionNotificationDelivery:
        """
        Attempt to deliver a notification for the first time.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError:
                If notification_id is None or blank, no notification
                is registered under it, or it already has a delivery
                attempt recorded
        """

        self._validate_id(notification_id, "notification ID")

        with self._lock:
            notification = self._resolve(notification_id)

            if self._deliveries_by_notification_id.get(notification_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                    f"Notification ID {notification_id!r} already has a delivery attempt recorded; use retry() "
                    "instead."
                )

            return self._attempt(notification)

    def retry(self, notification_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionNotificationDelivery:
        """
        Re-attempt delivery of a notification whose most recent
        attempt did not succeed.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError:
                If notification_id is None or blank, no notification
                is registered under it, it has no delivery attempt
                yet, or its most recent attempt already succeeded
        """

        self._validate_id(notification_id, "notification ID")

        with self._lock:
            notification = self._resolve(notification_id)
            attempts = self._deliveries_by_notification_id.get(notification_id)

            if not attempts:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                    f"Cannot retry notification ID {notification_id!r}: it has no delivery attempt yet; use "
                    "deliver() first."
                )

            if attempts[-1].delivered:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                    f"Cannot retry notification ID {notification_id!r}: it was already delivered."
                )

            return self._attempt(notification)

    def pending(self) -> tuple:
        """
        List every notification whose most recent delivery attempt,
        if any, has not succeeded, in publish order.
        """

        with self._lock:
            return tuple(
                notification
                for notification in self._notifications.values()
                if not self._latest_delivered(notification.notification_id)
            )

    def history(self, schedule_id: str) -> tuple:
        """
        List every notification published for a schedule, in publish
        order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            return tuple(
                self._notifications[notification_id]
                for notification_id in self._notification_ids_by_schedule_id.get(schedule_id, ())
            )

    def _attempt(
        self,
        notification: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleNotification,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionNotificationDelivery:
        succeeded = self._delivery_handler(notification) if self._delivery_handler is not None else True

        record = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionNotificationDelivery(
            notification_id=notification.notification_id,
            delivered=bool(succeeded),
            delivered_at=datetime.now(timezone.utc) if succeeded else None,
        )

        self._deliveries_by_notification_id.setdefault(notification.notification_id, []).append(record)

        return record

    def _latest_delivered(self, notification_id: str) -> bool:
        attempts = self._deliveries_by_notification_id.get(notification_id)

        return bool(attempts) and attempts[-1].delivered

    def _resolve(
        self,
        notification_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleNotification:
        notification = self._notifications.get(notification_id)

        if notification is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                f"No session schedule notification is registered under notification ID {notification_id!r}."
            )

        return notification

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError(
                f"Cannot operate with an empty or blank {label}."
            )
