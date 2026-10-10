import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleNotification as Notification,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionNotificationDelivery as Delivery,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingNotificationService as NotificationService,
)


class TestWorkspaceSessionSchedulingNotificationService:
    def test_publish_notification(self):
        service = NotificationService(recipients=("consumer-1", "consumer-2"))

        notification = service.publish("schedule-1", "created")

        assert isinstance(notification, Notification)
        assert notification.schedule_id == "schedule-1"
        assert notification.event == "created"
        assert notification.recipients == ("consumer-1", "consumer-2")

    def test_successful_delivery(self):
        service = NotificationService(recipients=("consumer-1",))
        notification = service.publish("schedule-1", "created")

        delivery = service.deliver(notification.notification_id)

        assert isinstance(delivery, Delivery)
        assert delivery.delivered is True
        assert delivery.delivered_at is not None
        assert service.pending() == ()

        with pytest.raises(Error):
            service.deliver(notification.notification_id)

    def test_retry_delivery(self):
        attempts = {"count": 0}

        def handler(notification):
            attempts["count"] += 1
            return attempts["count"] > 1

        service = NotificationService(recipients=("consumer-1",), delivery_handler=handler)
        notification = service.publish("schedule-1", "created")

        first = service.deliver(notification.notification_id)
        assert first.delivered is False
        assert first.delivered_at is None

        with pytest.raises(Error):
            service.deliver(notification.notification_id)

        second = service.retry(notification.notification_id)
        assert second.delivered is True
        assert second.delivered_at is not None

        with pytest.raises(Error):
            service.retry(notification.notification_id)

    def test_pending_notifications(self):
        service = NotificationService(recipients=("consumer-1",), delivery_handler=lambda notification: False)
        first = service.publish("schedule-1", "created")
        second = service.publish("schedule-2", "created")

        service.deliver(first.notification_id)

        pending_ids = {notification.notification_id for notification in service.pending()}
        assert pending_ids == {first.notification_id, second.notification_id}

    def test_history_lookup(self):
        service = NotificationService(recipients=("consumer-1",))
        first = service.publish("schedule-1", "created")
        second = service.publish("schedule-1", "dispatched")
        service.publish("schedule-2", "created")

        history = service.history("schedule-1")

        assert [notification.notification_id for notification in history] == [
            first.notification_id,
            second.notification_id,
        ]

        with pytest.raises(Error):
            service.history("   ")

    def test_duplicate_notification_rejection(self):
        service = NotificationService(recipients=("consumer-1",))
        service.publish("schedule-1", "created")

        with pytest.raises(Error):
            service.publish("schedule-1", "created")

        # a different event for the same schedule is not a duplicate
        service.publish("schedule-1", "dispatched")

        with pytest.raises(Error):
            service.publish("   ", "created")

        with pytest.raises(Error):
            NotificationService(recipients=())

        with pytest.raises(Error):
            service.deliver("unknown-notification")
