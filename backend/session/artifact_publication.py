from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_distribution_error import (
    ExecutionArtifactDistributionError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "PUBLISHED",
    }
)


@dataclass(frozen=True)
class ArtifactPublication:
    """
    Immutable record of a single execution artifact having been
    published to a distribution channel.

    The publication is a value object only. It performs no
    publishing of its own; creating and looking up publications is
    the responsibility of an execution artifact distribution service.

    Attributes:
        artifact_id: The identifier of the artifact that was
            published
        channel_id: The identifier of the channel it was published to
        publication_id: The publication's unique identifier
        status: The publication's status, currently always PUBLISHED
        published_at: When this publication took place
    """

    artifact_id: str

    channel_id: str

    publication_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    status: str = "PUBLISHED"

    published_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.channel_id, "channel ID")
        self._require_text(self.publication_id, "publication ID")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionArtifactDistributionError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.published_at, datetime):
            raise ExecutionArtifactDistributionError(
                "Cannot build an artifact publication with a non-datetime published_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionError(
                f"Cannot build an artifact publication with an empty or blank {field_name}."
            )
