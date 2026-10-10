from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_storage_integrity_check_error import (
    ExecutionStorageIntegrityCheckError,
)

STATUS_OK = "OK"

STATUS_CORRUPT = "CORRUPT"

STATUSES = (
    STATUS_OK,
    STATUS_CORRUPT,
)


@dataclass(frozen=True)
class ExecutionStorageIntegrityCheck:
    """
    Immutable record of a single checksum comparison performed
    against a volume or one of its replicas, to detect storage
    corruption.

    The check is a value object only. It performs no comparison of
    its own; comparing checksums and deciding OK versus CORRUPT is
    the responsibility of an execution storage integrity service,
    which produces a new record for every comparison rather than
    mutating an existing one. The record itself refuses to be built
    with a status inconsistent with its own checksums, so a mismatch
    can never be silently recorded as OK.

    Attributes:
        check_id: The check's unique identifier
        volume_id: The identifier of the volume this check was
            performed against
        target: What was checked -- PRIMARY for the volume itself, or
            a replica's target for a replica check
        expected_checksum: The canonical checksum the data was
            expected to match
        actual_checksum: The checksum actually found
        status: OK when the checksums matched exactly, CORRUPT
            otherwise
        checked_at: When the check was performed
    """

    check_id: str

    volume_id: str

    target: str

    expected_checksum: str

    actual_checksum: str

    status: str

    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.check_id, "check ID")
        self._require_text(self.volume_id, "volume ID")
        self._require_text(self.target, "target")
        self._require_text(self.expected_checksum, "expected checksum")
        self._require_text(self.actual_checksum, "actual checksum")

        if self.status not in STATUSES:
            raise ExecutionStorageIntegrityCheckError(
                f"Cannot build an execution storage integrity check with an unknown status: "
                f"{self.status!r}."
            )

        matches = self.expected_checksum == self.actual_checksum

        if self.status == STATUS_OK and not matches:
            raise ExecutionStorageIntegrityCheckError(
                "Cannot build an execution storage integrity check marked OK with mismatched "
                "checksums."
            )

        if self.status == STATUS_CORRUPT and matches:
            raise ExecutionStorageIntegrityCheckError(
                "Cannot build an execution storage integrity check marked CORRUPT with matching "
                "checksums."
            )

        if self.checked_at is None or not isinstance(self.checked_at, datetime):
            raise ExecutionStorageIntegrityCheckError(
                "Cannot build an execution storage integrity check with a non-datetime checked_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageIntegrityCheckError(
                f"Cannot build an execution storage integrity check with an empty or blank "
                f"{field_name}."
            )
