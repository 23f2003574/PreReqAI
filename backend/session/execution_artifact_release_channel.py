from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_release_channel_error import (
    ExecutionArtifactReleaseChannelError,
)

CHANNEL_CANARY = "CANARY"

CHANNEL_STABLE = "STABLE"

CHANNEL_LTS = "LTS"

CHANNELS = (
    CHANNEL_CANARY,
    CHANNEL_STABLE,
    CHANNEL_LTS,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_SUPERSEDED = "SUPERSEDED"

STATUS_ROLLED_BACK = "ROLLED_BACK"

STATUSES = (
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    STATUS_ROLLED_BACK,
)


@dataclass(frozen=True)
class ExecutionArtifactReleaseChannel:
    """
    Immutable record of a single artifact version's eligibility for
    consumption in a deployment channel.

    The record is a value object only. It performs no verification of
    its own; releasing, promoting, rolling back, and looking up
    channel entries is the responsibility of an execution artifact
    release channel service, which produces a new record for every
    transition rather than mutating an existing one.

    Attributes:
        artifact_id: The identifier of the artifact this entry
            belongs to
        version_id: The identifier of the version made eligible for
            consumption by this entry
        channel: The deployment channel this entry governs, one of
            CHANNELS
        status: ACTIVE while this entry is the channel's current
            version, SUPERSEDED once a later release replaces it, or
            ROLLED_BACK once explicitly reverted; one of STATUSES
        channel_id: The entry's unique identifier
        released_at: When this entry was created
    """

    artifact_id: str

    version_id: str

    channel: str

    status: str = STATUS_ACTIVE

    channel_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    released_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.channel_id, "channel entry ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.version_id, "version ID")

        if self.channel not in CHANNELS:
            raise ExecutionArtifactReleaseChannelError(
                f"Cannot build an execution artifact release channel entry with an unknown "
                f"channel: {self.channel!r}."
            )

        if self.status not in STATUSES:
            raise ExecutionArtifactReleaseChannelError(
                f"Cannot build an execution artifact release channel entry with an unknown "
                f"status: {self.status!r}."
            )

        if not isinstance(self.released_at, datetime):
            raise ExecutionArtifactReleaseChannelError(
                "Cannot build an execution artifact release channel entry with a non-datetime "
                "released_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactReleaseChannelError(
                f"Cannot build an execution artifact release channel entry with an empty or "
                f"blank {field_name}."
            )
