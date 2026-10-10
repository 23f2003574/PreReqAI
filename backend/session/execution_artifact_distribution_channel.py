from dataclasses import (
    dataclass,
)

from .execution_artifact_distribution_error import (
    ExecutionArtifactDistributionError,
)


@dataclass(frozen=True)
class ExecutionArtifactDistributionChannel:
    """
    Immutable description of a destination execution artifacts can
    be published to, such as a webhook, storage bucket, or message
    queue.

    The channel is a value object only. It performs no publishing of
    its own; registering, publishing to, disabling, and looking up
    channels is the responsibility of an execution artifact
    distribution service.

    Attributes:
        channel_id: The channel's unique identifier
        name: A human-readable name for the channel
        type: The kind of destination this channel is, e.g. "webhook"
            or "bucket"
        endpoint: Where published artifacts are delivered, e.g. a URL
            or bucket path
        enabled: Whether the channel currently accepts publishing
    """

    channel_id: str

    name: str

    type: str

    endpoint: str

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.channel_id, "channel ID")
        self._require_text(self.name, "name")
        self._require_text(self.type, "type")
        self._require_text(self.endpoint, "endpoint")

        if not isinstance(self.enabled, bool):
            raise ExecutionArtifactDistributionError(
                "Cannot build a distribution channel with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionError(
                f"Cannot build a distribution channel with an empty or blank {field_name}."
            )
