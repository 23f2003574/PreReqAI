from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
)

from uuid import uuid4

from .execution_artifact_distribution_receipt_error import (
    ExecutionArtifactDistributionReceiptError,
)


@dataclass(frozen=True)
class ExecutionArtifactDistributionReceipt:
    """
    Immutable, verifiable record that a single artifact delivery
    completed successfully.

    The receipt is a value object only. It performs no verification
    of its own; creating, looking up, verifying, and listing receipts
    is the responsibility of an execution artifact distribution
    receipt service. Once created, a receipt is never mutated: a
    receipt for a delivery is created at most once.

    Attributes:
        delivery_id: The identifier of the delivery this receipt
            attests to
        artifact_id: The identifier of the artifact that was
            delivered
        channel_id: The identifier of the channel it was delivered to
        checksum: A checksum binding this receipt to the delivery's
            state at the time the receipt was created
        delivered_at: When the delivery completed
        receipt_id: The receipt's unique identifier
    """

    delivery_id: str

    artifact_id: str

    channel_id: str

    checksum: str

    delivered_at: datetime

    receipt_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.delivery_id, "delivery ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.channel_id, "channel ID")
        self._require_text(self.checksum, "checksum")
        self._require_text(self.receipt_id, "receipt ID")

        if not isinstance(self.delivered_at, datetime):
            raise ExecutionArtifactDistributionReceiptError(
                "Cannot build a distribution receipt with a non-datetime delivered_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionReceiptError(
                f"Cannot build a distribution receipt with an empty or blank {field_name}."
            )
