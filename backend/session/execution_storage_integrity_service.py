from threading import (
    RLock,
)

from uuid import uuid4

from .execution_storage_replica import (
    STATUS_SYNCED,
)

from .execution_storage_integrity_check import (
    ExecutionStorageIntegrityCheck,
    STATUS_CORRUPT,
    STATUS_OK,
)

from .execution_storage_integrity_check_error import (
    ExecutionStorageIntegrityCheckError,
)

TARGET_PRIMARY = "PRIMARY"


class ExecutionStorageIntegrityService:
    """
    Detects storage corruption by verifying volume and replica
    checksums.

    Composes with:
    - an existing storage volume service (anything exposing
      `expected_checksum(volume_id) -> str`, the volume's canonical,
      trusted checksum, and `actual_checksum(volume_id) -> str`, a
      freshly computed checksum of what is currently stored)
    - an existing storage replication service (anything exposing
      `get(replica_id) -> object with .volume_id, .target, and
      .checksum`, and `sync(replica_id) -> object with .status`,
      the latter matching ExecutionStorageReplicationService)

    Behavior:
    - check() compares a volume's expected and actual checksums,
      recording an OK or CORRUPT result against target PRIMARY
    - check_replica() compares a replica's stored checksum against
      its source volume's expected checksum, recording an OK or
      CORRUPT result against the replica's target
    - repair() re-syncs a replica from its source, but only when the
      source volume's most recent direct (PRIMARY) check is OK; a
      source with no recorded direct check, or whose last direct
      check is CORRUPT, is rejected as unverified
    - history() reports every check recorded for a volume, oldest
      first, across both direct and replica checks

    Every comparison is recorded, matching or not: checksums are
    always compared exactly, and a mismatch is always marked CORRUPT
    rather than silently accepted.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, volume_service, replica_service):
        self._volume_service = volume_service
        self._replica_service = replica_service
        self._history_by_volume = {}
        self._lock = RLock()

    def check(self, volume_id: str) -> ExecutionStorageIntegrityCheck:
        """
        Compare volume_id's expected and actual checksums.

        Raises:
            ExecutionStorageIntegrityCheckError: If volume_id is None
                or blank, or it is unknown
        """

        self._validate_text(volume_id, "volume ID")

        expected = self._safe_checksum(self._volume_service.expected_checksum, volume_id)
        actual = self._safe_checksum(self._volume_service.actual_checksum, volume_id)

        return self._record(volume_id, TARGET_PRIMARY, expected, actual)

    def check_replica(self, replica_id: str) -> ExecutionStorageIntegrityCheck:
        """
        Compare replica_id's stored checksum against its source
        volume's expected checksum.

        Raises:
            ExecutionStorageIntegrityCheckError: If replica_id is None
                or blank, or it is unknown
        """

        self._validate_text(replica_id, "replica ID")

        replica = self._resolve_replica(replica_id)
        expected = self._safe_checksum(self._volume_service.expected_checksum, replica.volume_id)

        return self._record(replica.volume_id, replica.target, expected, replica.checksum)

    def repair(self, replica_id: str) -> ExecutionStorageIntegrityCheck:
        """
        Re-sync replica_id from its source volume, then record a
        fresh check confirming the result.

        Raises:
            ExecutionStorageIntegrityCheckError: If replica_id is None
                or blank, it is unknown, its source volume has no OK
                direct (PRIMARY) check on record, or the re-sync
                attempt does not produce a SYNCED replica
        """

        self._validate_text(replica_id, "replica ID")

        replica = self._resolve_replica(replica_id)

        with self._lock:
            history = self._history_by_volume.get(replica.volume_id, [])
            source_checks = [check for check in history if check.target == TARGET_PRIMARY]
            last = source_checks[-1] if source_checks else None

        if last is None or last.status != STATUS_OK:
            raise ExecutionStorageIntegrityCheckError(
                f"Cannot repair replica ID {replica_id!r}: source volume ID "
                f"{replica.volume_id!r} has not been verified."
            )

        try:
            repaired = self._replica_service.sync(replica_id)
        except Exception as error:
            raise ExecutionStorageIntegrityCheckError(
                f"Cannot repair replica ID {replica_id!r}: re-sync from its source failed."
            ) from error

        if repaired.status != STATUS_SYNCED:
            raise ExecutionStorageIntegrityCheckError(
                f"Cannot repair replica ID {replica_id!r}: re-sync from its source did not "
                f"succeed."
            )

        return self.check_replica(replica_id)

    def history(self, volume_id: str) -> tuple:
        """
        Every check recorded for volume_id, oldest first.
        """

        self._validate_text(volume_id, "volume ID")

        with self._lock:
            return tuple(self._history_by_volume.get(volume_id, ()))

    def _record(
        self, volume_id: str, target: str, expected: str, actual: str
    ) -> ExecutionStorageIntegrityCheck:
        status = STATUS_OK if expected == actual else STATUS_CORRUPT

        check = ExecutionStorageIntegrityCheck(
            check_id=str(uuid4()),
            volume_id=volume_id,
            target=target,
            expected_checksum=expected,
            actual_checksum=actual,
            status=status,
        )

        with self._lock:
            self._history_by_volume.setdefault(volume_id, []).append(check)

        return check

    def _resolve_replica(self, replica_id: str):
        try:
            return self._replica_service.get(replica_id)
        except Exception as error:
            raise ExecutionStorageIntegrityCheckError(
                f"Cannot resolve replica ID {replica_id!r}: it is unknown."
            ) from error

    @staticmethod
    def _safe_checksum(fn, volume_id: str) -> str:
        try:
            return fn(volume_id)
        except Exception as error:
            raise ExecutionStorageIntegrityCheckError(
                f"Cannot resolve volume ID {volume_id!r}: it is unknown."
            ) from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageIntegrityCheckError(f"Cannot use an empty or blank {field_name}.")
