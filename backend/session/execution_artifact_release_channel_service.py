from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_artifact_release_channel import (
    CHANNELS,
    STATUS_ACTIVE,
    STATUS_ROLLED_BACK,
    STATUS_SUPERSEDED,
    ExecutionArtifactReleaseChannel,
)

from .execution_artifact_release_channel_error import (
    ExecutionArtifactReleaseChannelError,
)


class ExecutionArtifactReleaseChannelService:
    """
    Controls which artifact versions are eligible for consumption in
    each deployment channel (CANARY, STABLE, LTS), using an existing
    integrity service to confirm a version currently passes its
    integrity check before it may be released or promoted.

    The service's responsibility is release channel bookkeeping only.
    It does not distribute artifact contents itself.

    Behavior:
    - release() admits only a verified version, and makes it the
      channel's current ACTIVE version, superseding whatever was
      current before it
    - Exactly one entry is ACTIVE per artifact/channel pair at a time
    - promote() only ever moves a version forward through CHANNELS; it
      never allows a sideways or backward move
    - rollback() restores the previously ACTIVE, still-verified
      version of a channel, marking the record it reverts as
      ROLLED_BACK
    - history() lists every entry ever recorded for an
      artifact/channel pair, oldest to newest

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, integrity_service):
        """
        Args:
            integrity_service: The service used to confirm a version
                currently passes its integrity check before it is
                released or promoted. Any object exposing
                `verify(version_id) -> bool` is accepted
        """

        self._integrity_service = integrity_service
        self._entries_by_id = {}
        self._entry_ids_by_key = {}
        self._lock = RLock()

    def release(self, artifact_id: str, version_id: str, channel: str) -> ExecutionArtifactReleaseChannel:
        """
        Make a verified version the current, ACTIVE version of a
        channel, superseding whatever was current before it.

        Raises:
            ExecutionArtifactReleaseChannelError: If artifact_id or
                version_id is None or blank, channel is not one of
                CHANNELS, or the version fails its integrity check
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")
        self._validate_channel(channel)

        with self._lock:
            self._ensure_verified(version_id)

            return self._activate(artifact_id, version_id, channel)

    def current(self, artifact_id: str, channel: str) -> ExecutionArtifactReleaseChannel:
        """
        Look up the current, ACTIVE version of a channel.

        Raises:
            ExecutionArtifactReleaseChannelError: If artifact_id is
                None or blank, channel is not one of CHANNELS, or no
                version is currently ACTIVE for the pair
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_channel(channel)

        with self._lock:
            entry = self._active_entry((artifact_id, channel))

            if entry is None:
                raise ExecutionArtifactReleaseChannelError(
                    f"No version is currently active for artifact ID {artifact_id!r} on channel "
                    f"{channel!r}."
                )

            return entry

    def promote(self, channel_id: str, target_channel: str) -> ExecutionArtifactReleaseChannel:
        """
        Promote the version behind a channel entry forward into
        target_channel.

        Raises:
            ExecutionArtifactReleaseChannelError: If channel_id is
                None or blank, no entry is registered under it,
                target_channel is not one of CHANNELS, target_channel
                is not strictly forward of the entry's own channel, or
                the version fails its integrity check
        """

        self._validate_id(channel_id, "channel entry ID")
        self._validate_channel(target_channel)

        with self._lock:
            source = self._resolve(channel_id)

            if CHANNELS.index(target_channel) <= CHANNELS.index(source.channel):
                raise ExecutionArtifactReleaseChannelError(
                    f"Cannot promote from {source.channel!r} to {target_channel!r}: promotion "
                    f"only moves forward."
                )

            self._ensure_verified(source.version_id)

            return self._activate(source.artifact_id, source.version_id, target_channel)

    def rollback(self, channel_id: str) -> ExecutionArtifactReleaseChannel:
        """
        Restore a channel's previously ACTIVE, still-verified version,
        marking the entry being reverted ROLLED_BACK.

        Raises:
            ExecutionArtifactReleaseChannelError: If channel_id is
                None or blank, no entry is registered under it, it is
                not currently ACTIVE, no earlier version was ever
                active for its artifact/channel pair, or that earlier
                version no longer passes its integrity check
        """

        self._validate_id(channel_id, "channel entry ID")

        with self._lock:
            current_entry = self._resolve(channel_id)

            if current_entry.status != STATUS_ACTIVE:
                raise ExecutionArtifactReleaseChannelError(
                    f"Cannot roll back channel entry ID {channel_id!r}: it is not currently "
                    f"active."
                )

            key = (current_entry.artifact_id, current_entry.channel)
            ids = self._entry_ids_by_key.get(key, [])
            position = ids.index(channel_id)

            previous_entry = None

            for earlier_id in reversed(ids[:position]):
                candidate = self._entries_by_id[earlier_id]

                if candidate.status == STATUS_SUPERSEDED:
                    previous_entry = candidate
                    break

            if previous_entry is None:
                raise ExecutionArtifactReleaseChannelError(
                    f"Cannot roll back channel entry ID {channel_id!r}: no earlier version is "
                    f"available for artifact ID {current_entry.artifact_id!r} on channel "
                    f"{current_entry.channel!r}."
                )

            self._ensure_verified(previous_entry.version_id)

            rolled_back = replace(current_entry, status=STATUS_ROLLED_BACK)
            self._entries_by_id[channel_id] = rolled_back

            return self._activate(previous_entry.artifact_id, previous_entry.version_id, previous_entry.channel)

    def history(self, artifact_id: str, channel: str) -> tuple:
        """
        List every entry ever recorded for an artifact/channel pair,
        oldest to newest.

        Raises:
            ExecutionArtifactReleaseChannelError: If artifact_id is
                None or blank, or channel is not one of CHANNELS
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_channel(channel)

        with self._lock:
            return tuple(
                self._entries_by_id[entry_id] for entry_id in self._entry_ids_by_key.get((artifact_id, channel), [])
            )

    def _activate(self, artifact_id: str, version_id: str, channel: str) -> ExecutionArtifactReleaseChannel:
        key = (artifact_id, channel)

        previous_active = self._active_entry(key)

        if previous_active is not None:
            superseded = replace(previous_active, status=STATUS_SUPERSEDED)
            self._entries_by_id[previous_active.channel_id] = superseded

        entry = ExecutionArtifactReleaseChannel(
            artifact_id=artifact_id,
            version_id=version_id,
            channel=channel,
        )

        self._entries_by_id[entry.channel_id] = entry
        self._entry_ids_by_key.setdefault(key, []).append(entry.channel_id)

        return entry

    def _active_entry(self, key):
        for entry_id in self._entry_ids_by_key.get(key, []):
            entry = self._entries_by_id[entry_id]

            if entry.status == STATUS_ACTIVE:
                return entry

        return None

    def _ensure_verified(self, version_id: str) -> None:
        try:
            verified = self._integrity_service.verify(version_id)
        except Exception as error:
            raise ExecutionArtifactReleaseChannelError(
                f"Cannot verify version ID {version_id!r}: it failed its integrity check."
            ) from error

        if not verified:
            raise ExecutionArtifactReleaseChannelError(
                f"Cannot release version ID {version_id!r}: it failed its integrity check."
            )

    def _resolve(self, channel_id: str) -> ExecutionArtifactReleaseChannel:
        entry = self._entries_by_id.get(channel_id)

        if entry is None:
            raise ExecutionArtifactReleaseChannelError(
                f"No channel entry is registered under channel entry ID {channel_id!r}."
            )

        return entry

    @staticmethod
    def _validate_channel(channel: str) -> None:
        if channel not in CHANNELS:
            raise ExecutionArtifactReleaseChannelError(f"Cannot use an unknown channel: {channel!r}.")

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactReleaseChannelError(f"Cannot use an empty or blank {field_name}.")
