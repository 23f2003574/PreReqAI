from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .artifact_distribution_delivery import (
    ArtifactDistributionDelivery,
)

from .execution_artifact_distribution_delivery_error import (
    ExecutionArtifactDistributionDeliveryError,
)


class ExecutionArtifactDistributionDeliveryService:
    """
    Tracks each artifact's delivery to its batch's distribution
    channel independently, including retries and final status, using
    an existing distribution batch service to resolve which channel a
    batch delivers to and an existing execution artifact distribution
    service to actually attempt delivery.

    The service's responsibility is delivery bookkeeping only. It
    does not decide which channel a batch targets or move artifact
    contents itself.

    Behavior:
    - An artifact may have at most one delivery per channel; create()
      rejects a second delivery for an artifact/channel pair already
      tracked
    - deliver() makes a delivery's first attempt and requires it to
      be PENDING
    - retry() makes a further attempt and requires the delivery to be
      FAILED; a DELIVERED (completed) delivery may never be retried
    - An attempt that fails is recorded as FAILED rather than raising:
      the caller observes the outcome via status() or the returned
      record, not by catching an exception
    - Every attempt, successful or not, increments attempts

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, distribution_batch_service, execution_artifact_distribution_service):
        """
        Args:
            distribution_batch_service: The service used to resolve
                the channel a batch delivers to. Any object exposing
                `get(batch_id)` (returning an object with a
                `.channel_id`), raising if the batch is unknown, is
                accepted
            execution_artifact_distribution_service: The service used
                to actually attempt delivery of an artifact to a
                channel. Any object exposing
                `publish(artifact_id, channel_id)`, raising if the
                attempt fails, is accepted
        """

        self._distribution_batch_service = distribution_batch_service
        self._execution_artifact_distribution_service = execution_artifact_distribution_service
        self._deliveries_by_id = {}
        self._delivery_ids_by_batch = {}
        self._delivery_id_by_artifact_channel = {}
        self._lock = RLock()

    def create(self, batch_id: str, artifact_id: str) -> ArtifactDistributionDelivery:
        """
        Create a pending delivery tracking one artifact's delivery to
        its batch's channel.

        Raises:
            ExecutionArtifactDistributionDeliveryError: If batch_id or
                artifact_id is None or blank, the distribution batch
                service does not recognize batch_id, or the artifact
                already has a delivery tracked for that channel
        """

        self._validate_id(batch_id, "batch ID")
        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            channel_id = self._resolve_batch_channel(batch_id)

            if (artifact_id, channel_id) in self._delivery_id_by_artifact_channel:
                raise ExecutionArtifactDistributionDeliveryError(
                    f"Artifact ID {artifact_id!r} already has a delivery tracked for channel ID "
                    f"{channel_id!r}."
                )

            delivery = ArtifactDistributionDelivery(
                batch_id=batch_id,
                artifact_id=artifact_id,
                channel_id=channel_id,
            )

            self._deliveries_by_id[delivery.delivery_id] = delivery
            self._delivery_ids_by_batch.setdefault(batch_id, []).append(delivery.delivery_id)
            self._delivery_id_by_artifact_channel[(artifact_id, channel_id)] = delivery.delivery_id

            return delivery

    def deliver(self, delivery_id: str) -> ArtifactDistributionDelivery:
        """
        Make a delivery's first attempt.

        Raises:
            ExecutionArtifactDistributionDeliveryError: If delivery_id
                is None or blank, no delivery is registered under it,
                or it is not PENDING
        """

        self._validate_id(delivery_id, "delivery ID")

        with self._lock:
            delivery = self._resolve(delivery_id)

            if delivery.status != "PENDING":
                raise ExecutionArtifactDistributionDeliveryError(
                    f"Cannot deliver delivery ID {delivery_id!r}: it is {delivery.status}, not PENDING."
                )

            return self._attempt(delivery)

    def retry(self, delivery_id: str) -> ArtifactDistributionDelivery:
        """
        Make a further attempt at a delivery that previously failed.

        Raises:
            ExecutionArtifactDistributionDeliveryError: If delivery_id
                is None or blank, no delivery is registered under it,
                or it is not FAILED (in particular, a completed
                DELIVERED delivery may never be retried)
        """

        self._validate_id(delivery_id, "delivery ID")

        with self._lock:
            delivery = self._resolve(delivery_id)

            if delivery.status != "FAILED":
                raise ExecutionArtifactDistributionDeliveryError(
                    f"Cannot retry delivery ID {delivery_id!r}: it is {delivery.status}, not FAILED."
                )

            return self._attempt(delivery)

    def status(self, delivery_id: str) -> ArtifactDistributionDelivery:
        """
        Look up a delivery's current record.

        Raises:
            ExecutionArtifactDistributionDeliveryError: If delivery_id
                is None or blank, or no delivery is registered under
                it
        """

        self._validate_id(delivery_id, "delivery ID")

        with self._lock:
            return self._resolve(delivery_id)

    def pending(self, batch_id: str) -> list:
        """
        List a batch's deliveries that have not yet succeeded (status
        PENDING or FAILED), in the order they were created.

        Raises:
            ExecutionArtifactDistributionDeliveryError: If batch_id is
                None or blank
        """

        self._validate_id(batch_id, "batch ID")

        with self._lock:
            return [
                self._deliveries_by_id[delivery_id]
                for delivery_id in self._delivery_ids_by_batch.get(batch_id, [])
                if self._deliveries_by_id[delivery_id].status != "DELIVERED"
            ]

    def _attempt(self, delivery: ArtifactDistributionDelivery) -> ArtifactDistributionDelivery:
        attempts = delivery.attempts + 1

        try:
            self._execution_artifact_distribution_service.publish(delivery.artifact_id, delivery.channel_id)
        except Exception:
            updated = replace(delivery, status="FAILED", attempts=attempts)
        else:
            updated = replace(
                delivery,
                status="DELIVERED",
                attempts=attempts,
                delivered_at=datetime.now(timezone.utc),
            )

        self._deliveries_by_id[delivery.delivery_id] = updated

        return updated

    def _resolve_batch_channel(self, batch_id: str) -> str:
        try:
            return self._distribution_batch_service.get(batch_id).channel_id
        except Exception as error:
            raise ExecutionArtifactDistributionDeliveryError(
                f"No distribution batch is known under batch ID {batch_id!r}."
            ) from error

    def _resolve(self, delivery_id: str) -> ArtifactDistributionDelivery:
        delivery = self._deliveries_by_id.get(delivery_id)

        if delivery is None:
            raise ExecutionArtifactDistributionDeliveryError(
                f"No delivery is registered under delivery ID {delivery_id!r}."
            )

        return delivery

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionDeliveryError(f"Cannot use an empty or blank {field_name}.")
