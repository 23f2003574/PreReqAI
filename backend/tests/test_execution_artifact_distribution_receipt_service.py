from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ExecutionArtifactDistributionReceipt,
    ExecutionArtifactDistributionReceiptError as Error,
    ExecutionArtifactDistributionReceiptService,
)


class _DeliveryRecord:
    def __init__(self, delivery_id, artifact_id, channel_id, status, delivered_at):
        self.delivery_id = delivery_id
        self.artifact_id = artifact_id
        self.channel_id = channel_id
        self.status = status
        self.delivered_at = delivered_at


class _DeliveryTrackingStub:
    """Stand-in for the delivery tracking service assumed by this commit."""

    def __init__(self):
        self._records = {}

    def track(self, delivery_id, artifact_id, channel_id, status="DELIVERED", delivered_at=None):
        record = _DeliveryRecord(
            delivery_id=delivery_id,
            artifact_id=artifact_id,
            channel_id=channel_id,
            status=status,
            delivered_at=delivered_at or datetime.now(timezone.utc),
        )
        self._records[delivery_id] = record
        return record

    def status(self, delivery_id):
        record = self._records.get(delivery_id)

        if record is None:
            raise KeyError(delivery_id)

        return record


def _build():
    delivery_tracking = _DeliveryTrackingStub()
    receipt_service = ExecutionArtifactDistributionReceiptService(delivery_tracking)
    return delivery_tracking, receipt_service


class TestExecutionArtifactDistributionReceiptService:
    def test_create_receipt(self):
        delivery_tracking, receipt_service = _build()
        delivery_tracking.track("delivery-1", "artifact-1", "channel-1")

        receipt = receipt_service.create("delivery-1")

        assert isinstance(receipt, ExecutionArtifactDistributionReceipt)
        assert receipt.delivery_id == "delivery-1"
        assert receipt.artifact_id == "artifact-1"
        assert receipt.channel_id == "channel-1"
        assert receipt.checksum != ""

        delivery_tracking.track("delivery-2", "artifact-2", "channel-1", status="PENDING")

        with pytest.raises(Error):
            receipt_service.create("delivery-2")

    def test_verify_receipt(self):
        delivery_tracking, receipt_service = _build()
        delivery_tracking.track("delivery-1", "artifact-1", "channel-1")
        receipt = receipt_service.create("delivery-1")

        assert receipt_service.verify(receipt.receipt_id) is True

    def test_list_receipts(self):
        delivery_tracking, receipt_service = _build()
        delivery_tracking.track("delivery-1", "artifact-1", "channel-1")
        delivery_tracking.track("delivery-2", "artifact-1", "channel-2")

        first = receipt_service.create("delivery-1")
        second = receipt_service.create("delivery-2")

        listed = receipt_service.list("artifact-1")

        assert [entry.receipt_id for entry in listed] == [first.receipt_id, second.receipt_id]

    def test_duplicate_rejection(self):
        delivery_tracking, receipt_service = _build()
        delivery_tracking.track("delivery-1", "artifact-1", "channel-1")
        receipt_service.create("delivery-1")

        with pytest.raises(Error):
            receipt_service.create("delivery-1")

    def test_checksum_mismatch(self):
        delivery_tracking, receipt_service = _build()
        record = delivery_tracking.track("delivery-1", "artifact-1", "channel-1")
        receipt = receipt_service.create("delivery-1")

        record.delivered_at = datetime.now(timezone.utc)

        assert receipt_service.verify(receipt.receipt_id) is False
