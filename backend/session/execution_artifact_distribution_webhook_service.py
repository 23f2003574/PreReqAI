from threading import (
    RLock,
)

from .execution_artifact_distribution_webhook import (
    SUPPORTED_EVENTS,
    ExecutionArtifactDistributionWebhook,
)

from .execution_artifact_distribution_webhook_error import (
    ExecutionArtifactDistributionWebhookError,
)


class ExecutionArtifactDistributionWebhookService:
    """
    Notifies subscribed external endpoints when deliveries to a
    distribution channel complete or fail, using an existing delivery
    tracking service to resolve which channel a delivery belongs to,
    and a notifier to actually attempt each notification.

    The service's responsibility is subscription and dispatch
    bookkeeping only. It does not send an HTTP request itself; that
    is delegated to the notifier given at construction time.

    Behavior:
    - dispatch() notifies only enabled webhooks subscribed to the
      given event, on the delivery's own channel; every other
      registered webhook is skipped
    - A (delivery_id, event) pair may be dispatched at most once;
      dispatch() rejects a repeat, since re-attempting a failed
      notification is retry()'s job, not dispatch()'s
    - A notification attempt that fails leaves that webhook/event
      pending: it remains retryable until it succeeds
    - retry() re-attempts every currently pending notification for a
      webhook/event pair

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_distribution_delivery_service, notifier):
        """
        Args:
            execution_artifact_distribution_delivery_service: The
                service used to resolve the channel a delivery
                belongs to. Any object exposing `status(delivery_id)`
                (returning an object with a `.channel_id`), raising if
                the delivery is unknown, is accepted
            notifier: The collaborator used to actually attempt a
                notification. Any callable accepting
                (webhook, delivery_id, event) and raising if the
                attempt fails is accepted
        """

        self._execution_artifact_distribution_delivery_service = execution_artifact_distribution_delivery_service
        self._notifier = notifier
        self._webhooks_by_id = {}
        self._webhook_ids_by_channel = {}
        self._dispatched_delivery_events = set()
        self._delivered_keys = set()
        self._pending_by_key = {}
        self._lock = RLock()

    def register(self, webhook: ExecutionArtifactDistributionWebhook) -> ExecutionArtifactDistributionWebhook:
        """
        Register a new webhook subscription.

        Raises:
            ExecutionArtifactDistributionWebhookError: If webhook is
                not an ExecutionArtifactDistributionWebhook, or its
                webhook ID is already registered
        """

        if not isinstance(webhook, ExecutionArtifactDistributionWebhook):
            raise ExecutionArtifactDistributionWebhookError(
                "Cannot register an invalid webhook: webhook must be an ExecutionArtifactDistributionWebhook."
            )

        with self._lock:
            if webhook.webhook_id in self._webhooks_by_id:
                raise ExecutionArtifactDistributionWebhookError(
                    f"Webhook ID {webhook.webhook_id!r} is already registered."
                )

            self._webhooks_by_id[webhook.webhook_id] = webhook
            self._webhook_ids_by_channel.setdefault(webhook.channel_id, []).append(webhook.webhook_id)

            return webhook

    def remove(self, webhook_id: str) -> ExecutionArtifactDistributionWebhook:
        """
        Remove a webhook subscription.

        Raises:
            ExecutionArtifactDistributionWebhookError: If webhook_id is
                None or blank, or no webhook is registered under it
        """

        self._validate_id(webhook_id, "webhook ID")

        with self._lock:
            webhook = self._resolve_webhook(webhook_id)

            del self._webhooks_by_id[webhook_id]
            self._webhook_ids_by_channel[webhook.channel_id].remove(webhook_id)

            return webhook

    def dispatch(self, delivery_id: str, event: str) -> list:
        """
        Notify every enabled webhook subscribed to event on the
        delivery's channel.

        Returns:
            The list of webhooks successfully notified this call.
            Webhooks skipped as disabled or unsubscribed, and
            webhooks whose notification attempt failed (left pending
            for retry()), are excluded

        Raises:
            ExecutionArtifactDistributionWebhookError: If delivery_id
                or event is None or blank, event is not DELIVERED or
                FAILED, the delivery tracking service does not
                recognize delivery_id, or this (delivery_id, event)
                pair has already been dispatched
        """

        self._validate_id(delivery_id, "delivery ID")

        normalized_event = self._normalize_event(event)

        with self._lock:
            key = (delivery_id, normalized_event)

            if key in self._dispatched_delivery_events:
                raise ExecutionArtifactDistributionWebhookError(
                    f"Delivery ID {delivery_id!r} has already had event {normalized_event!r} dispatched."
                )

            channel_id = self._delivery_channel(delivery_id)

            notified = []

            for webhook_id in self._webhook_ids_by_channel.get(channel_id, []):
                webhook = self._webhooks_by_id[webhook_id]

                if not webhook.enabled or normalized_event not in webhook.events:
                    continue

                if self._attempt(webhook, delivery_id, normalized_event):
                    notified.append(webhook)

            self._dispatched_delivery_events.add(key)

            return notified

    def retry(self, webhook_id: str, event: str) -> list:
        """
        Re-attempt every currently pending notification for a
        webhook/event pair.

        Returns:
            The list of delivery IDs that were retried this call

        Raises:
            ExecutionArtifactDistributionWebhookError: If webhook_id or
                event is None or blank, event is not DELIVERED or
                FAILED, or no webhook is registered under webhook_id
        """

        self._validate_id(webhook_id, "webhook ID")

        normalized_event = self._normalize_event(event)

        with self._lock:
            webhook = self._resolve_webhook(webhook_id)

            pending_key = (webhook_id, normalized_event)
            delivery_ids = list(self._pending_by_key.get(pending_key, {}).keys())

            for delivery_id in delivery_ids:
                self._attempt(webhook, delivery_id, normalized_event)

            return delivery_ids

    def pending(self) -> list:
        """
        List every notification currently pending retry, as
        {"webhook_id", "delivery_id", "event", "attempts"} dicts.
        """

        with self._lock:
            entries = []

            for (webhook_id, event), by_delivery in self._pending_by_key.items():
                for delivery_id, attempts in by_delivery.items():
                    entries.append(
                        {
                            "webhook_id": webhook_id,
                            "delivery_id": delivery_id,
                            "event": event,
                            "attempts": attempts,
                        }
                    )

            return entries

    def _attempt(self, webhook: ExecutionArtifactDistributionWebhook, delivery_id: str, event: str) -> bool:
        pending_key = (webhook.webhook_id, event)
        delivered_key = (webhook.webhook_id, delivery_id, event)

        attempts = self._pending_by_key.get(pending_key, {}).get(delivery_id, 0) + 1

        try:
            self._notifier(webhook, delivery_id, event)
        except Exception:
            self._pending_by_key.setdefault(pending_key, {})[delivery_id] = attempts

            return False
        else:
            self._delivered_keys.add(delivered_key)
            by_delivery = self._pending_by_key.get(pending_key)

            if by_delivery is not None:
                by_delivery.pop(delivery_id, None)

                if not by_delivery:
                    del self._pending_by_key[pending_key]

            return True

    def _delivery_channel(self, delivery_id: str) -> str:
        try:
            return self._execution_artifact_distribution_delivery_service.status(delivery_id).channel_id
        except Exception as error:
            raise ExecutionArtifactDistributionWebhookError(
                f"No delivery is known under delivery ID {delivery_id!r}."
            ) from error

    def _resolve_webhook(self, webhook_id: str) -> ExecutionArtifactDistributionWebhook:
        webhook = self._webhooks_by_id.get(webhook_id)

        if webhook is None:
            raise ExecutionArtifactDistributionWebhookError(
                f"No webhook is registered under webhook ID {webhook_id!r}."
            )

        return webhook

    @staticmethod
    def _normalize_event(event: str) -> str:
        if event is None or not event.strip():
            raise ExecutionArtifactDistributionWebhookError("Cannot use an empty or blank event.")

        normalized = event.strip().upper()

        if normalized not in SUPPORTED_EVENTS:
            raise ExecutionArtifactDistributionWebhookError(
                f"Unsupported event {event!r}: expected one of {sorted(SUPPORTED_EVENTS)}."
            )

        return normalized

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionWebhookError(f"Cannot use an empty or blank {field_name}.")
