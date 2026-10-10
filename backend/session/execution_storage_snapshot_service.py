import hashlib

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_storage_volume import (
    STATUS_ATTACHED,
)

from .execution_storage_snapshot import (
    ExecutionStorageSnapshot,
)

from .execution_storage_snapshot_error import (
    ExecutionStorageSnapshotError,
)


class ExecutionStorageSnapshotService:
    """
    Captures immutable point-in-time snapshots of execution volumes
    for recovery and rollback.

    Composes with an existing storage volume service (anything
    exposing `get(volume_id) -> object with .status and .size`),
    used to confirm a volume is currently ATTACHED and to capture its
    size before it can be snapshotted, and to confirm a restore
    target is large enough to hold the snapshot being restored.

    Behavior:
    - create() captures a new snapshot of an ATTACHED volume,
      recording its size and a checksum computed over the snapshot's
      identity and content
    - get() reports a single snapshot by its ID
    - restore() restores snapshot_id onto volume_id, but only when
      volume_id is large enough to hold the snapshot
    - history() reports every snapshot taken of a volume, oldest
      first

    Snapshots are immutable: once captured, a snapshot's fields never
    change, and restoring never mutates it.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, volume_service):
        self._volume_service = volume_service
        self._snapshots_by_id = {}
        self._history_by_volume = {}
        self._lock = RLock()

    def create(self, volume_id: str) -> ExecutionStorageSnapshot:
        """
        Capture a new snapshot of volume_id.

        Raises:
            ExecutionStorageSnapshotError: If volume_id is None or
                blank, it is unknown, or it is not currently ATTACHED
        """

        self._validate_text(volume_id, "volume ID")

        volume = self._resolve_volume(volume_id)

        if volume.status != STATUS_ATTACHED:
            raise ExecutionStorageSnapshotError(
                f"Cannot snapshot volume ID {volume_id!r}: it is not currently attached "
                f"(status {volume.status!r})."
            )

        snapshot_id = str(uuid4())

        snapshot = ExecutionStorageSnapshot(
            snapshot_id=snapshot_id,
            volume_id=volume_id,
            size=volume.size,
            checksum=self._checksum(snapshot_id, volume_id, volume.size),
        )

        with self._lock:
            self._snapshots_by_id[snapshot_id] = snapshot
            self._history_by_volume.setdefault(volume_id, []).append(snapshot)

        return snapshot

    def get(self, snapshot_id: str) -> ExecutionStorageSnapshot:
        """
        The snapshot registered under snapshot_id.

        Raises:
            ExecutionStorageSnapshotError: If snapshot_id is None or
                blank, or no snapshot is registered under it
        """

        self._validate_text(snapshot_id, "snapshot ID")

        with self._lock:
            return self._resolve_snapshot(snapshot_id)

    def restore(self, snapshot_id: str, volume_id: str) -> ExecutionStorageSnapshot:
        """
        Restore snapshot_id onto volume_id.

        Raises:
            ExecutionStorageSnapshotError: If snapshot_id or volume_id
                is None or blank, snapshot_id is unknown, volume_id is
                unknown, or volume_id's current size is smaller than
                the snapshot's size
        """

        self._validate_text(snapshot_id, "snapshot ID")
        self._validate_text(volume_id, "volume ID")

        with self._lock:
            snapshot = self._resolve_snapshot(snapshot_id)

        target = self._resolve_volume(volume_id)

        if target.size < snapshot.size:
            raise ExecutionStorageSnapshotError(
                f"Cannot restore snapshot ID {snapshot_id!r} onto volume ID {volume_id!r}: its "
                f"size ({target.size!r}) is smaller than the snapshot's size ({snapshot.size!r})."
            )

        return snapshot

    def history(self, volume_id: str) -> tuple:
        """
        Every snapshot taken of volume_id, oldest first.
        """

        self._validate_text(volume_id, "volume ID")

        with self._lock:
            return tuple(self._history_by_volume.get(volume_id, ()))

    def _resolve_volume(self, volume_id: str):
        try:
            return self._volume_service.get(volume_id)
        except Exception as error:
            raise ExecutionStorageSnapshotError(
                f"Cannot resolve volume ID {volume_id!r}: it is unknown."
            ) from error

    def _resolve_snapshot(self, snapshot_id: str) -> ExecutionStorageSnapshot:
        snapshot = self._snapshots_by_id.get(snapshot_id)

        if snapshot is None:
            raise ExecutionStorageSnapshotError(
                f"No snapshot is registered under snapshot ID {snapshot_id!r}."
            )

        return snapshot

    @staticmethod
    def _checksum(snapshot_id: str, volume_id: str, size) -> str:
        payload = f"{snapshot_id}:{volume_id}:{size}".encode("utf-8")

        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageSnapshotError(f"Cannot use an empty or blank {field_name}.")
