from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
)

from typing import Optional
from uuid import uuid4

from .execution_artifact_distribution_delivery_error import (
    ExecutionArtifactDistributionDeliveryError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "PENDING",
        "DELIVERED",
        "FAILED",
    }
)


@dataclass(frozen=True)
class ArtifactDistributionDelivery:
    """
    Immutable record tracking a single artifact's delivery to a
    single distribution channel, independent of any other delivery
    in the same batch.

    The delivery is a value object only. It performs no delivery of
    its own; creating, attempting, retrying, and looking up
    deliveries is the responsibility of an execution artifact
    distribution delivery service.

    Attributes:
        delivery_id: The delivery's unique identifier
        batch_id: The identifier of the batch this delivery belongs
            to
        artifact_id: The identifier of the artifact being delivered
        channel_id: The identifier of the channel the artifact is
            being delivered to
        status: The delivery's current status, one of PENDING,
            DELIVERED, or FAILED
        attempts: How many delivery attempts have been made
        delivered_at: When the delivery succeeded, or None if it has
            not (yet) succeeded
    """

    batch_id: str

    artifact_id: str

    channel_id: str

    delivery_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    status: str = "PENDING"

    attempts: int = 0

    delivered_at: Optional[datetime] = None

    def __post_init__(self):
        self._require_text(self.delivery_id, "delivery ID")
        self._require_text(self.batch_id, "batch ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.channel_id, "channel ID")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionArtifactDistributionDeliveryError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.attempts, int) or isinstance(self.attempts, bool):
            raise ExecutionArtifactDistributionDeliveryError(
                "Cannot build a distribution delivery with a non-integer attempts."
            )

        if self.attempts < 0:
            raise ExecutionArtifactDistributionDeliveryError(
                "Cannot build a distribution delivery with a negative attempts."
            )

        if self.delivered_at is not None and not isinstance(self.delivered_at, datetime):
            raise ExecutionArtifactDistributionDeliveryError(
                "Cannot build a distribution delivery with a non-datetime delivered_at."
            )

        if self.status == "DELIVERED" and self.delivered_at is None:
            raise ExecutionArtifactDistributionDeliveryError(
                "Cannot build a DELIVERED distribution delivery without delivered_at."
            )

        if self.status != "DELIVERED" and self.delivered_at is not None:
            raise ExecutionArtifactDistributionDeliveryError(
                f"Cannot build a {self.status} distribution delivery with delivered_at set."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionDeliveryError(
                f"Cannot build a distribution delivery with an empty or blank {field_name}."
            )
