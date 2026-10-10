from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .artifact_publication import (
    ArtifactPublication,
)

from .execution_artifact_distribution_channel import (
    ExecutionArtifactDistributionChannel,
)

from .execution_artifact_distribution_error import (
    ExecutionArtifactDistributionError,
)


class ExecutionArtifactDistributionService:
    """
    Publishes execution artifacts to registered distribution
    channels (e.g. webhooks, buckets, or message queues), using an
    existing execution artifact registry to confirm an artifact is
    genuinely known before it is published.

    The service's responsibility is channel and publication
    bookkeeping only. It does not deliver artifact contents to a
    channel's endpoint itself.

    Behavior:
    - Channel IDs are unique: register() rejects a channel ID that is
      already registered
    - A disabled channel rejects publish(); disable() takes effect
      immediately
    - status() reports a channel's most recently recorded publication

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_service):
        """
        Args:
            execution_artifact_service: The registry used to confirm
                an artifact ID is known before it is published. Any
                object exposing `get(artifact_id)`, raising if the
                artifact is unknown, is accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._channels_by_id = {}
        self._latest_publication_by_channel = {}
        self._lock = RLock()

    def register(self, channel: ExecutionArtifactDistributionChannel) -> ExecutionArtifactDistributionChannel:
        """
        Register a new distribution channel.

        Raises:
            ExecutionArtifactDistributionError: If channel is not an
                ExecutionArtifactDistributionChannel, or its channel
                ID is already registered
        """

        if not isinstance(channel, ExecutionArtifactDistributionChannel):
            raise ExecutionArtifactDistributionError(
                "Cannot register an invalid channel: channel must be an ExecutionArtifactDistributionChannel."
            )

        with self._lock:
            if channel.channel_id in self._channels_by_id:
                raise ExecutionArtifactDistributionError(
                    f"Channel ID {channel.channel_id!r} is already registered."
                )

            self._channels_by_id[channel.channel_id] = channel

            return channel

    def publish(self, artifact_id: str, channel_id: str) -> ArtifactPublication:
        """
        Publish an artifact to a registered, enabled channel.

        Raises:
            ExecutionArtifactDistributionError: If artifact_id or
                channel_id is None or blank, the execution artifact
                registry does not recognize artifact_id, no channel
                is registered under channel_id, or the channel is
                disabled
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(channel_id, "channel ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)
            channel = self._resolve(channel_id)

            if not channel.enabled:
                raise ExecutionArtifactDistributionError(
                    f"Cannot publish to channel ID {channel_id!r}: it is disabled."
                )

            publication = ArtifactPublication(artifact_id=artifact_id, channel_id=channel_id)
            self._latest_publication_by_channel[channel_id] = publication

            return publication

    def disable(self, channel_id: str) -> ExecutionArtifactDistributionChannel:
        """
        Disable a registered channel so it rejects future publishing.

        Raises:
            ExecutionArtifactDistributionError: If channel_id is None
                or blank, or no channel is registered under it
        """

        self._validate_id(channel_id, "channel ID")

        with self._lock:
            channel = self._resolve(channel_id)
            disabled = replace(channel, enabled=False)
            self._channels_by_id[channel_id] = disabled

            return disabled

    def channels(self) -> list:
        """
        List every registered channel, in the order they were
        registered.
        """

        with self._lock:
            return list(self._channels_by_id.values())

    def status(self, channel_id: str) -> ArtifactPublication:
        """
        Look up a channel's most recently recorded publication.

        Raises:
            ExecutionArtifactDistributionError: If channel_id is None
                or blank, no channel is registered under it, or the
                channel has no recorded publication yet
        """

        self._validate_id(channel_id, "channel ID")

        with self._lock:
            self._resolve(channel_id)

            publication = self._latest_publication_by_channel.get(channel_id)

            if publication is None:
                raise ExecutionArtifactDistributionError(
                    f"Channel ID {channel_id!r} has no recorded publication yet."
                )

            return publication

    def _resolve(self, channel_id: str) -> ExecutionArtifactDistributionChannel:
        channel = self._channels_by_id.get(channel_id)

        if channel is None:
            raise ExecutionArtifactDistributionError(
                f"No channel is registered under channel ID {channel_id!r}."
            )

        return channel

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactDistributionError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionError(f"Cannot use an empty or blank {field_name}.")
