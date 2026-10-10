import hashlib

from threading import (
    RLock,
)

from .execution_artifact_distribution_receipt import (
    ExecutionArtifactDistributionReceipt,
)

from .execution_artifact_distribution_receipt_error import (
    ExecutionArtifactDistributionReceiptError,
)


class ExecutionArtifactDistributionReceiptService:
    """
    Records verifiable receipts for successful artifact deliveries,
    using an existing delivery tracking service as the source of
    truth for whether, and to where, a delivery completed.

    The service's responsibility is receipt bookkeeping only. A
    receipt is never issued for anything but a successful delivery,
    and once issued is never mutated or reissued.

    Behavior:
    - A receipt may only be created for a delivery that is currently
      DELIVERED
    - A delivery may have at most one receipt; create() rejects a
      delivery ID that already has one
    - Each receipt's checksum is computed deterministically from its
      delivery's identity and completion time, binding the receipt to
      that exact delivery
    - verify() is read-only: it recomputes the expected checksum from
      the delivery's current state and compares it to the receipt's
      recorded checksum, without mutating either

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_distribution_delivery_service):
        """
        Args:
            execution_artifact_distribution_delivery_service: The
                service used to confirm a delivery succeeded and to
                look up its current state. Any object exposing
                `status(delivery_id)` (returning an object with
                `.status`, `.artifact_id`, `.channel_id`, and
                `.delivered_at`), raising if the delivery is unknown,
                is accepted
        """

        self._execution_artifact_distribution_delivery_service = execution_artifact_distribution_delivery_service
        self._receipts_by_id = {}
        self._receipt_id_by_delivery = {}
        self._receipt_ids_by_artifact = {}
        self._lock = RLock()

    def create(self, delivery_id: str) -> ExecutionArtifactDistributionReceipt:
        """
        Create a receipt for a successfully delivered delivery.

        Raises:
            ExecutionArtifactDistributionReceiptError: If delivery_id
                is None or blank, the delivery tracking service does
                not recognize delivery_id, the delivery is not
                DELIVERED, or delivery_id already has a receipt
        """

        self._validate_id(delivery_id, "delivery ID")

        with self._lock:
            if delivery_id in self._receipt_id_by_delivery:
                raise ExecutionArtifactDistributionReceiptError(
                    f"Delivery ID {delivery_id!r} already has a recorded receipt."
                )

            delivery = self._delivery_status(delivery_id)

            if delivery.status != "DELIVERED":
                raise ExecutionArtifactDistributionReceiptError(
                    f"Cannot create a receipt for delivery ID {delivery_id!r}: it is {delivery.status}, not "
                    "DELIVERED."
                )

            receipt = ExecutionArtifactDistributionReceipt(
                delivery_id=delivery_id,
                artifact_id=delivery.artifact_id,
                channel_id=delivery.channel_id,
                checksum=self._compute_checksum(delivery),
                delivered_at=delivery.delivered_at,
            )

            self._receipts_by_id[receipt.receipt_id] = receipt
            self._receipt_id_by_delivery[delivery_id] = receipt.receipt_id
            self._receipt_ids_by_artifact.setdefault(delivery.artifact_id, []).append(receipt.receipt_id)

            return receipt

    def get(self, receipt_id: str) -> ExecutionArtifactDistributionReceipt:
        """
        Look up a single receipt.

        Raises:
            ExecutionArtifactDistributionReceiptError: If receipt_id
                is None or blank, or no receipt is known under it
        """

        self._validate_id(receipt_id, "receipt ID")

        with self._lock:
            return self._resolve(receipt_id)

    def verify(self, receipt_id: str) -> bool:
        """
        Confirm a receipt's checksum still matches its delivery's
        current state. Read-only: never mutates the receipt or the
        delivery.

        Raises:
            ExecutionArtifactDistributionReceiptError: If receipt_id
                is None or blank, no receipt is known under it, or its
                delivery is no longer known to the delivery tracking
                service
        """

        self._validate_id(receipt_id, "receipt ID")

        with self._lock:
            receipt = self._resolve(receipt_id)
            delivery = self._delivery_status(receipt.delivery_id)

            return self._compute_checksum(delivery) == receipt.checksum

    def list(self, artifact_id: str) -> list:
        """
        List every receipt issued for an artifact, in the order they
        were created.

        Raises:
            ExecutionArtifactDistributionReceiptError: If artifact_id
                is None or blank
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return [
                self._receipts_by_id[receipt_id]
                for receipt_id in self._receipt_ids_by_artifact.get(artifact_id, [])
            ]

    @staticmethod
    def _compute_checksum(delivery) -> str:
        canonical = f"{delivery.delivery_id}:{delivery.artifact_id}:{delivery.channel_id}:{delivery.delivered_at.isoformat()}"

        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _delivery_status(self, delivery_id: str):
        try:
            return self._execution_artifact_distribution_delivery_service.status(delivery_id)
        except Exception as error:
            raise ExecutionArtifactDistributionReceiptError(
                f"No delivery is known under delivery ID {delivery_id!r}."
            ) from error

    def _resolve(self, receipt_id: str) -> ExecutionArtifactDistributionReceipt:
        receipt = self._receipts_by_id.get(receipt_id)

        if receipt is None:
            raise ExecutionArtifactDistributionReceiptError(f"No receipt is known under receipt ID {receipt_id!r}.")

        return receipt

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionReceiptError(f"Cannot use an empty or blank {field_name}.")
