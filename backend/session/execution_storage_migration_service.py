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

from .execution_storage_migration import (
    ExecutionStorageMigration,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_IN_PROGRESS,
    STATUS_ROLLED_BACK,
    STATUS_VERIFIED,
)

from .execution_storage_migration_error import (
    ExecutionStorageMigrationError,
)


class ExecutionStorageMigrationService:
    """
    Moves a volume between storage targets without losing integrity
    or interrupting active mounts.

    Composes with:
    - an existing storage failover service (anything exposing
      `select(volume_id) -> str` and `register(volume_id, targets)`,
      matching ExecutionStorageFailoverService), used to determine a
      volume's currently active source target, and to cut runtime
      access over to the destination once a migration completes
    - an existing storage replication service (anything exposing
      `replicate(volume_id, target) -> object with .replica_id and
      .checksum`, `verify(replica_id) -> object with .checksum`, and
      `remove(replica_id)`, matching
      ExecutionStorageReplicationService), used to copy the volume
      onto its destination, verify the copy's checksum, and discard
      it on rollback
    - a destination capacity service (anything exposing
      `has_capacity(destination) -> bool`), used to confirm a
      destination has room before a migration starts

    Behavior:
    - start() confirms the destination has capacity and differs from
      the volume's current source target, then replicates the volume
      onto it, recording an IN_PROGRESS migration; the source is
      never touched
    - verify() confirms the destination's checksum still matches what
      was captured at the start of the migration; a mismatch moves
      the migration to FAILED rather than raising, since a failed
      migration remains rollbackable
    - complete() finalizes a VERIFIED migration, cutting runtime
      access over to the destination target; it refuses to complete
      anything that has not been verified, so a checksum must match
      before completion
    - rollback() discards the destination copy and abandons the
      migration, from any state short of COMPLETED or an earlier
      ROLLED_BACK
    - status() reports a migration's current status

    The source target is preserved untouched throughout every state
    but COMPLETED: it is only ever superseded, never deleted, by this
    service.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, failover_service, replica_service, capacity_service):
        self._failover_service = failover_service
        self._replica_service = replica_service
        self._capacity_service = capacity_service
        self._migrations_by_id = {}
        self._replica_by_migration = {}
        self._lock = RLock()

    def start(self, volume_id: str, destination: str) -> ExecutionStorageMigration:
        """
        Start migrating volume_id onto destination.

        Raises:
            ExecutionStorageMigrationError: If volume_id or
                destination is None or blank, destination does not
                have capacity, volume_id has no currently active
                source target, destination is already that source
                target, or the underlying replication attempt fails
        """

        self._validate_text(volume_id, "volume ID")
        self._validate_text(destination, "destination")

        if not self._has_capacity(destination):
            raise ExecutionStorageMigrationError(
                f"Cannot migrate volume ID {volume_id!r} to destination {destination!r}: it "
                f"does not have capacity."
            )

        source_target = self._safe_call(self._failover_service.select, volume_id)

        if source_target is None:
            raise ExecutionStorageMigrationError(
                f"Cannot migrate volume ID {volume_id!r}: it has no currently active source "
                f"target."
            )

        if source_target == destination:
            raise ExecutionStorageMigrationError(
                f"Cannot migrate volume ID {volume_id!r} to {destination!r}: it is already its "
                f"current source target."
            )

        replica = self._safe_call(self._replica_service.replicate, volume_id, destination)

        migration = ExecutionStorageMigration(
            migration_id=str(uuid4()),
            volume_id=volume_id,
            source_target=source_target,
            destination_target=destination,
            status=STATUS_IN_PROGRESS,
            checksum=replica.checksum,
        )

        with self._lock:
            self._migrations_by_id[migration.migration_id] = migration
            self._replica_by_migration[migration.migration_id] = replica.replica_id

        return migration

    def verify(self, migration_id: str) -> ExecutionStorageMigration:
        """
        Confirm migration_id's destination checksum still matches
        what was captured at the start of the migration. A mismatch
        moves the migration to FAILED rather than raising.

        Raises:
            ExecutionStorageMigrationError: If migration_id is None or
                blank, or no migration is registered under it
        """

        self._validate_text(migration_id, "migration ID")

        with self._lock:
            migration = self._resolve(migration_id)
            replica_id = self._replica_by_migration[migration_id]

        try:
            verified = self._replica_service.verify(replica_id)
            matches = verified.checksum == migration.checksum
        except Exception:
            matches = False

        updated = replace(migration, status=STATUS_VERIFIED if matches else STATUS_FAILED)

        with self._lock:
            self._migrations_by_id[migration_id] = updated

        return updated

    def complete(self, migration_id: str) -> ExecutionStorageMigration:
        """
        Finalize migration_id, cutting runtime access over to its
        destination target.

        Raises:
            ExecutionStorageMigrationError: If migration_id is None or
                blank, no migration is registered under it, or it is
                not currently VERIFIED
        """

        self._validate_text(migration_id, "migration ID")

        with self._lock:
            migration = self._resolve(migration_id)

            if migration.status != STATUS_VERIFIED:
                raise ExecutionStorageMigrationError(
                    f"Cannot complete migration ID {migration_id!r}: it is not currently "
                    f"VERIFIED (status {migration.status!r})."
                )

        self._safe_call(
            self._failover_service.register,
            migration.volume_id,
            [migration.destination_target, migration.source_target],
        )

        completed = replace(
            migration, status=STATUS_COMPLETED, completed_at=datetime.now(timezone.utc)
        )

        with self._lock:
            self._migrations_by_id[migration_id] = completed

        return completed

    def rollback(self, migration_id: str) -> ExecutionStorageMigration:
        """
        Discard migration_id's destination copy and abandon it.

        Raises:
            ExecutionStorageMigrationError: If migration_id is None or
                blank, no migration is registered under it, or it is
                already COMPLETED or ROLLED_BACK
        """

        self._validate_text(migration_id, "migration ID")

        with self._lock:
            migration = self._resolve(migration_id)

            if migration.status in (STATUS_COMPLETED, STATUS_ROLLED_BACK):
                raise ExecutionStorageMigrationError(
                    f"Cannot roll back migration ID {migration_id!r}: it is already "
                    f"{migration.status!r}."
                )

            replica_id = self._replica_by_migration.get(migration_id)

        if replica_id is not None:
            try:
                self._replica_service.remove(replica_id)
            except Exception:
                pass

        rolled_back = replace(migration, status=STATUS_ROLLED_BACK)

        with self._lock:
            self._migrations_by_id[migration_id] = rolled_back

        return rolled_back

    def status(self, migration_id: str) -> str:
        """
        The current status of migration_id.

        Raises:
            ExecutionStorageMigrationError: If migration_id is None or
                blank, or no migration is registered under it
        """

        self._validate_text(migration_id, "migration ID")

        with self._lock:
            return self._resolve(migration_id).status

    def _has_capacity(self, destination: str) -> bool:
        try:
            return bool(self._capacity_service.has_capacity(destination))
        except Exception:
            return False

    def _resolve(self, migration_id: str) -> ExecutionStorageMigration:
        migration = self._migrations_by_id.get(migration_id)

        if migration is None:
            raise ExecutionStorageMigrationError(
                f"No migration is registered under migration ID {migration_id!r}."
            )

        return migration

    @staticmethod
    def _safe_call(fn, *args):
        try:
            return fn(*args)
        except Exception as error:
            raise ExecutionStorageMigrationError(f"Cannot resolve: {error}") from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageMigrationError(f"Cannot use an empty or blank {field_name}.")
