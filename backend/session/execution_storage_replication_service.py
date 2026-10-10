import hashlib

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

from uuid import uuid4

from .execution_storage_volume import (
    STATUS_ATTACHED,
)

from .execution_storage_replica import (
    ExecutionStorageReplica,
    STATUS_FAILED,
    STATUS_SYNCED,
)

from .execution_storage_replica_error import (
    ExecutionStorageReplicaError,
)


class ExecutionStorageReplicationService:
    """
    Replicates execution volumes across storage targets for
    durability and failover.

    Composes with an existing storage volume service (anything
    exposing `status(volume_id) -> str`, matching
    ExecutionStorageVolumeService), used to confirm a volume is
    currently active (ATTACHED) before it can be replicated or synced.

    Behavior:
    - replicate() admits a new SYNCED replica of an active volume onto
      a target, but only when the volume/target pair holds no other
      replica; the checksum is verified as part of this initial sync
    - sync() re-syncs an existing replica: when its source volume is
      still active, it produces a fresh checksum and moves it to
      SYNCED; otherwise the sync fails and the replica moves to
      FAILED without raising, preserving its last known checksum so
      it remains retryable
    - verify() confirms a replica is SYNCED and its checksum matches
      what a sync of it would currently produce
    - remove() permanently removes a replica
    - replicas() reports every replica tracked for a volume, across
      every target

    Each volume/target pair holds at most one tracked replica at a
    time.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, volume_service):
        self._volume_service = volume_service
        self._replicas_by_id = {}
        self._lock = RLock()

    def replicate(self, volume_id: str, target: str) -> ExecutionStorageReplica:
        """
        Replicate volume_id onto target.

        Raises:
            ExecutionStorageReplicaError: If volume_id or target is
                None or blank, volume_id is unknown or not currently
                active, or a replica already exists for the
                volume/target pair
        """

        self._validate_text(volume_id, "volume ID")
        self._validate_text(target, "target")

        status = self._current_status(volume_id)

        if status != STATUS_ATTACHED:
            raise ExecutionStorageReplicaError(
                f"Cannot replicate volume ID {volume_id!r}: it is not currently active "
                f"(status {status!r})."
            )

        with self._lock:
            for existing in self._replicas_by_id.values():
                if existing.volume_id == volume_id and existing.target == target:
                    raise ExecutionStorageReplicaError(
                        f"Cannot replicate volume ID {volume_id!r} to target {target!r}: a "
                        f"replica already exists for that pair."
                    )

            replica_id = str(uuid4())

            replica = ExecutionStorageReplica(
                replica_id=replica_id,
                volume_id=volume_id,
                target=target,
                status=STATUS_SYNCED,
                checksum=self._checksum(replica_id, volume_id, target),
            )

            self._replicas_by_id[replica_id] = replica

            return replica

    def sync(self, replica_id: str) -> ExecutionStorageReplica:
        """
        Re-sync replica_id against its source volume.

        Never raises for a source volume that is unknown or not
        currently active: the replica is instead moved to FAILED,
        remaining retryable.

        Raises:
            ExecutionStorageReplicaError: If replica_id is None or
                blank, or no replica is registered under it
        """

        self._validate_text(replica_id, "replica ID")

        with self._lock:
            replica = self._resolve(replica_id)

            if self._safe_status(replica.volume_id) != STATUS_ATTACHED:
                failed = replace(replica, status=STATUS_FAILED)
                self._replicas_by_id[replica_id] = failed

                return failed

            synced = replace(
                replica,
                status=STATUS_SYNCED,
                checksum=self._checksum(replica.replica_id, replica.volume_id, replica.target),
                replicated_at=datetime.now(timezone.utc),
            )

            self._replicas_by_id[replica_id] = synced

            return synced

    def verify(self, replica_id: str) -> ExecutionStorageReplica:
        """
        Confirm replica_id is SYNCED and its checksum is intact.

        Raises:
            ExecutionStorageReplicaError: If replica_id is None or
                blank, no replica is registered under it, it is not
                currently SYNCED, or its checksum does not match what
                a sync of it would currently produce
        """

        self._validate_text(replica_id, "replica ID")

        with self._lock:
            replica = self._resolve(replica_id)

            if replica.status != STATUS_SYNCED:
                raise ExecutionStorageReplicaError(
                    f"Cannot verify replica ID {replica_id!r}: it is not currently synced "
                    f"(status {replica.status!r})."
                )

            expected = self._checksum(replica.replica_id, replica.volume_id, replica.target)

            if replica.checksum != expected:
                raise ExecutionStorageReplicaError(
                    f"Checksum mismatch for replica ID {replica_id!r}: expected {expected!r}, "
                    f"found {replica.checksum!r}."
                )

            return replica

    def remove(self, replica_id: str) -> ExecutionStorageReplica:
        """
        Permanently remove replica_id.

        Raises:
            ExecutionStorageReplicaError: If replica_id is None or
                blank, or no replica is registered under it
        """

        self._validate_text(replica_id, "replica ID")

        with self._lock:
            replica = self._resolve(replica_id)
            del self._replicas_by_id[replica_id]

            return replica

    def replicas(self, volume_id: str) -> tuple:
        """
        Every replica tracked for volume_id, across every target.
        """

        self._validate_text(volume_id, "volume ID")

        with self._lock:
            return tuple(
                replica for replica in self._replicas_by_id.values() if replica.volume_id == volume_id
            )

    def _current_status(self, volume_id: str) -> str:
        try:
            return self._volume_service.status(volume_id)
        except Exception as error:
            raise ExecutionStorageReplicaError(
                f"Cannot resolve volume ID {volume_id!r}: it is unknown."
            ) from error

    def _safe_status(self, volume_id: str):
        try:
            return self._volume_service.status(volume_id)
        except Exception:
            return None

    def _resolve(self, replica_id: str) -> ExecutionStorageReplica:
        replica = self._replicas_by_id.get(replica_id)

        if replica is None:
            raise ExecutionStorageReplicaError(
                f"No replica is registered under replica ID {replica_id!r}."
            )

        return replica

    @staticmethod
    def _checksum(replica_id: str, volume_id: str, target: str) -> str:
        payload = f"{replica_id}:{volume_id}:{target}".encode("utf-8")

        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageReplicaError(f"Cannot use an empty or blank {field_name}.")
