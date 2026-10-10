import pytest

from backend.session import (
    ExecutionArtifactDistributionWebhook,
    ExecutionArtifactDistributionWebhookError as Error,
    ExecutionArtifactDistributionWebhookService,
)


class _Delivery:
    def __init__(self, delivery_id, channel_id):
        self.delivery_id = delivery_id
        self.channel_id = channel_id


class _DeliveryTrackingStub:
    """Stand-in for the delivery tracking service assumed by this commit."""

    def __init__(self):
        self._deliveries = {}

    def track(self, delivery_id, channel_id):
        self._deliveries[delivery_id] = _Delivery(delivery_id, channel_id)
        return self._deliveries[delivery_id]

    def status(self, delivery_id):
        delivery = self._deliveries.get(delivery_id)

        if delivery is None:
            raise KeyError(delivery_id)

        return delivery


class _NotifierStub:
    def __init__(self):
        self.calls = []
        self._fail_once_for = set()

    def fail_next(self, webhook_id):
        self._fail_once_for.add(webhook_id)

    def __call__(self, webhook, delivery_id, event):
        self.calls.append((webhook.webhook_id, delivery_id, event))

        if webhook.webhook_id in self._fail_once_for:
            self._fail_once_for.discard(webhook.webhook_id)
            raise RuntimeError("simulated notification failure")


def _build():
    delivery_tracking = _DeliveryTrackingStub()
    notifier = _NotifierStub()
    webhook_service = ExecutionArtifactDistributionWebhookService(delivery_tracking, notifier)
    return delivery_tracking, notifier, webhook_service


def _webhook(webhook_id="webhook-1", channel_id="channel-1", events=("DELIVERED",), enabled=True):
    return ExecutionArtifactDistributionWebhook(
        webhook_id=webhook_id,
        channel_id=channel_id,
        endpoint=f"https://example.test/webhooks/{webhook_id}",
        events=frozenset(events),
        enabled=enabled,
    )


class TestExecutionArtifactDistributionWebhookService:
    def test_register_and_remove(self):
        delivery_tracking, _notifier, webhook_service = _build()
        delivery_tracking.track("delivery-1", "channel-1")
        delivery_tracking.track("delivery-2", "channel-1")

        registered = webhook_service.register(_webhook())
        assert isinstance(registered, ExecutionArtifactDistributionWebhook)

        notified = webhook_service.dispatch("delivery-1", "DELIVERED")
        assert [w.webhook_id for w in notified] == ["webhook-1"]

        removed = webhook_service.remove("webhook-1")
        assert removed.webhook_id == "webhook-1"

        with pytest.raises(Error):
            webhook_service.remove("webhook-1")

        notified_after_removal = webhook_service.dispatch("delivery-2", "DELIVERED")
        assert notified_after_removal == []

    def test_matching_event_dispatch(self):
        delivery_tracking, notifier, webhook_service = _build()
        delivery_tracking.track("delivery-1", "channel-1")
        webhook_service.register(_webhook(events=("DELIVERED", "FAILED")))

        notified = webhook_service.dispatch("delivery-1", "DELIVERED")

        assert [w.webhook_id for w in notified] == ["webhook-1"]
        assert notifier.calls == [("webhook-1", "delivery-1", "DELIVERED")]
        assert webhook_service.pending() == []

    def test_ignored_event(self):
        delivery_tracking, notifier, webhook_service = _build()
        delivery_tracking.track("delivery-1", "channel-1")
        webhook_service.register(_webhook(events=("DELIVERED",)))

        notified = webhook_service.dispatch("delivery-1", "FAILED")

        assert notified == []
        assert notifier.calls == []

    def test_failed_delivery_retry(self):
        delivery_tracking, notifier, webhook_service = _build()
        delivery_tracking.track("delivery-1", "channel-1")
        webhook_service.register(_webhook())
        notifier.fail_next("webhook-1")

        notified = webhook_service.dispatch("delivery-1", "DELIVERED")

        assert notified == []
        pending = webhook_service.pending()
        assert len(pending) == 1
        assert pending[0]["webhook_id"] == "webhook-1"
        assert pending[0]["delivery_id"] == "delivery-1"
        assert pending[0]["attempts"] == 1

        retried = webhook_service.retry("webhook-1", "DELIVERED")

        assert retried == ["delivery-1"]
        assert webhook_service.pending() == []
        assert notifier.calls == [
            ("webhook-1", "delivery-1", "DELIVERED"),
            ("webhook-1", "delivery-1", "DELIVERED"),
        ]

    def test_duplicate_delivery_rejection(self):
        delivery_tracking, _notifier, webhook_service = _build()
        delivery_tracking.track("delivery-1", "channel-1")
        webhook_service.register(_webhook())

        webhook_service.dispatch("delivery-1", "DELIVERED")

        with pytest.raises(Error):
            webhook_service.dispatch("delivery-1", "DELIVERED")
