from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from numbers import (
    Real,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_storage_volume import (
    STATUS_ATTACHED,
)

from .execution_storage_garbage_record import (
    ExecutionStorageGarbageRecord,
    RESOURCE_REPLICA,
    RESOURCE_SNAPSHOT,
    RESOURCE_VOLUME,
)

from .execution_storage_garbage_record_error import (
    ExecutionStorageGarbageRecordError,
)

REASON_UNUSED = "no active attachment or mounts"


class ExecutionStorageGarbageCollectionService:
    """
    Automatically reclaims unused volumes, snapshots, and replicas
    without ever collecting active or attached storage.

    Composes with:
    - an existing storage volume service (anything exposing
      `status(volume_id) -> str`, matching
      ExecutionStorageVolumeService, plus `for_scope(scope_id) ->
      tuple of objects with .volume_id` and `scope_of(volume_id) ->
      str`), used to enumerate a scope's volumes and confirm whether
      a volume is currently attached
    - an existing storage mount service (anything exposing
      `volume_mounts(volume_id) -> tuple`, matching
      ExecutionStorageMountService), used to confirm a volume holds
      no active mounts
    - an existing storage snapshot service (anything exposing
      `history(volume_id) -> tuple of objects with .snapshot_id` and
      `get(snapshot_id) -> object with .volume_id`, matching
      ExecutionStorageSnapshotService), used to enumerate and resolve
      a volume's snapshots
    - an existing storage replication service (anything exposing
      `replicas(volume_id) -> tuple of objects with .replica_id` and
      `get(replica_id) -> object with .volume_id`, the former
      matching ExecutionStorageReplicationService), used to enumerate
      and resolve a volume's replicas

    A volume is unused when it is not currently ATTACHED and holds no
    active mounts; its snapshots and replicas are unused right along
    with it.

    Behavior:
    - scan() marks every unused resource found under a scope
    - mark() marks a single resource, but only when its volume is
      currently unused
    - collect() reclaims every pending mark for a scope whose
      retention window has elapsed and whose volume is still unused
      at the moment of collection, leaving everything else untouched;
      already-collected marks are skipped, so repeated calls are
      idempotent
    - protected() reports whether a resource is currently active or
      attached, and therefore ineligible for collection
    - history() reports every mark ever made for a scope, oldest
      first, whether or not it has since been collected

    Marking always happens before deletion: a resource is only ever
    reclaimed by moving an existing mark's deleted_at forward, never
    by deleting outright.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, volume_service, mount_service, snapshot_service, replica_service, retention_seconds=0):
        if (
            retention_seconds is None
            or isinstance(retention_seconds, bool)
            or not isinstance(retention_seconds, Real)
            or retention_seconds < 0
        ):
            raise ExecutionStorageGarbageRecordError(
                f"Cannot use a negative retention_seconds: {retention_seconds!r}."
            )

        self._volume_service = volume_service
        self._mount_service = mount_service
        self._snapshot_service = snapshot_service
        self._replica_service = replica_service
        self._retention_seconds = retention_seconds
        self._records_by_id = {}
        self._pending_by_resource = {}
        self._history_by_scope = {}
        self._lock = RLock()

    def scan(self, scope_id: str) -> tuple:
        """
        Mark every unused resource found under scope_id.

        Raises:
            ExecutionStorageGarbageRecordError: If scope_id is None or
                blank
        """

        self._validate_text(scope_id, "scope ID")

        volumes = self._safe_call(self._volume_service.for_scope, scope_id)

        marked = []

        for volume in volumes:
            if not self._volume_unused(volume.volume_id):
                continue

            marked.append(self._mark_resource(volume.volume_id, RESOURCE_VOLUME, scope_id))

            for snapshot in self._safe_call(self._snapshot_service.history, volume.volume_id):
                marked.append(self._mark_resource(snapshot.snapshot_id, RESOURCE_SNAPSHOT, scope_id))

            for replica in self._safe_call(self._replica_service.replicas, volume.volume_id):
                marked.append(self._mark_resource(replica.replica_id, RESOURCE_REPLICA, scope_id))

        return tuple(marked)

    def mark(self, resource_id: str) -> ExecutionStorageGarbageRecord:
        """
        Mark a single resource for collection.

        Raises:
            ExecutionStorageGarbageRecordError: If resource_id is None
                or blank, it is unknown, or its volume is currently
                active or attached
        """

        self._validate_text(resource_id, "resource ID")

        resource_type, volume_id = self._classify(resource_id)

        if not self._volume_unused(volume_id):
            raise ExecutionStorageGarbageRecordError(
                f"Cannot mark resource ID {resource_id!r}: its volume is active or attached."
            )

        scope_id = self._safe_call(self._volume_service.scope_of, volume_id)

        return self._mark_resource(resource_id, resource_type, scope_id)

    def collect(self, scope_id: str) -> tuple:
        """
        Reclaim every pending mark for scope_id whose retention window
        has elapsed and whose volume is still unused. Already-
        collected marks are left untouched, so repeated calls are
        idempotent.

        Raises:
            ExecutionStorageGarbageRecordError: If scope_id is None or
                blank
        """

        self._validate_text(scope_id, "scope ID")

        now = datetime.now(timezone.utc)
        collected = []

        with self._lock:
            history = self._history_by_scope.get(scope_id, [])

            for index, record in enumerate(history):
                if record.deleted_at is not None:
                    continue

                if (now - record.marked_at).total_seconds() < self._retention_seconds:
                    continue

                try:
                    _, volume_id = self._classify(record.resource_id)
                except ExecutionStorageGarbageRecordError:
                    volume_id = None

                if volume_id is not None and not self._volume_unused(volume_id):
                    continue

                updated = replace(record, deleted_at=now)
                history[index] = updated
                self._records_by_id[record.record_id] = updated
                self._pending_by_resource.pop(record.resource_id, None)
                collected.append(updated)

        return tuple(collected)

    def protected(self, resource_id: str) -> bool:
        """
        Whether resource_id is currently active or attached, and
        therefore ineligible for collection.

        Raises:
            ExecutionStorageGarbageRecordError: If resource_id is None
                or blank, or it is unknown
        """

        self._validate_text(resource_id, "resource ID")

        _, volume_id = self._classify(resource_id)

        return not self._volume_unused(volume_id)

    def history(self, scope_id: str) -> tuple:
        """
        Every mark ever made for scope_id, oldest first, whether or
        not it has since been collected.
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            return tuple(self._history_by_scope.get(scope_id, ()))

    def _mark_resource(self, resource_id: str, resource_type: str, scope_id: str) -> ExecutionStorageGarbageRecord:
        with self._lock:
            existing = self._pending_by_resource.get(resource_id)

            if existing is not None:
                return existing

            record = ExecutionStorageGarbageRecord(
                record_id=str(uuid4()),
                resource_id=resource_id,
                resource_type=resource_type,
                reason=REASON_UNUSED,
            )

            self._records_by_id[record.record_id] = record
            self._pending_by_resource[resource_id] = record
            self._history_by_scope.setdefault(scope_id, []).append(record)

            return record

    def _classify(self, resource_id: str):
        try:
            self._volume_service.status(resource_id)

            return RESOURCE_VOLUME, resource_id
        except Exception:
            pass

        try:
            snapshot = self._snapshot_service.get(resource_id)

            return RESOURCE_SNAPSHOT, snapshot.volume_id
        except Exception:
            pass

        try:
            replica = self._replica_service.get(resource_id)

            return RESOURCE_REPLICA, replica.volume_id
        except Exception:
            pass

        raise ExecutionStorageGarbageRecordError(
            f"Cannot resolve resource ID {resource_id!r}: it is unknown."
        )

    def _volume_unused(self, volume_id: str) -> bool:
        try:
            status = self._volume_service.status(volume_id)
        except Exception:
            return False

        if status == STATUS_ATTACHED:
            return False

        mounts = self._safe_call(self._mount_service.volume_mounts, volume_id)

        return len(mounts) == 0

    @staticmethod
    def _safe_call(fn, *args):
        try:
            return fn(*args)
        except Exception as error:
            raise ExecutionStorageGarbageRecordError(f"Cannot resolve: {error}") from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageGarbageRecordError(f"Cannot use an empty or blank {field_name}.")
