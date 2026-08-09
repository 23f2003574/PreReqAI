from dataclasses import (
    dataclass,
)

from .execution_artifact_distribution_webhook_error import (
    ExecutionArtifactDistributionWebhookError,
)

SUPPORTED_EVENTS = frozenset(
    {
        "DELIVERED",
        "FAILED",
    }
)


@dataclass(frozen=True)
class ExecutionArtifactDistributionWebhook:
    """
    Immutable subscription notifying an external endpoint when
    deliveries to a distribution channel complete or fail.

    The webhook is a value object only. It performs no notification
    of its own; registering, removing, dispatching to, and retrying
    webhooks is the responsibility of an execution artifact
    distribution webhook service.

    Attributes:
        webhook_id: The webhook's unique identifier
        channel_id: The identifier of the distribution channel this
            webhook is notified about
        endpoint: Where notifications are sent, e.g. a URL
        events: The delivery events this webhook is subscribed to, a
            non-empty subset of DELIVERED and FAILED
        enabled: Whether the webhook currently receives notifications
    """

    webhook_id: str

    channel_id: str

    endpoint: str

    events: frozenset

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.webhook_id, "webhook ID")
        self._require_text(self.channel_id, "channel ID")
        self._require_text(self.endpoint, "endpoint")

        if not isinstance(self.enabled, bool):
            raise ExecutionArtifactDistributionWebhookError(
                "Cannot build a distribution webhook with a non-bool enabled."
            )

        if self.events is None:
            raise ExecutionArtifactDistributionWebhookError(
                "Cannot build a distribution webhook with an empty or blank events."
            )

        events_list = list(self.events)

        if not events_list:
            raise ExecutionArtifactDistributionWebhookError(
                "Cannot build a distribution webhook with an empty or blank events."
            )

        normalized_events = frozenset(
            event.strip().upper() for event in events_list if isinstance(event, str) and event.strip()
        )

        if len(normalized_events) != len(set(events_list)):
            raise ExecutionArtifactDistributionWebhookError(
                "Cannot build a distribution webhook with a blank or non-string event."
            )

        unsupported = normalized_events - SUPPORTED_EVENTS

        if unsupported:
            raise ExecutionArtifactDistributionWebhookError(
                f"Unsupported event(s) {sorted(unsupported)}: expected a subset of {sorted(SUPPORTED_EVENTS)}."
            )

        object.__setattr__(self, "events", normalized_events)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionWebhookError(
                f"Cannot build a distribution webhook with an empty or blank {field_name}."
            )
