from threading import (
    RLock,
)

from uuid import uuid4

from .execution_storage_replica import (
    STATUS_SYNCED,
)

from .execution_storage_integrity_check import (
    STATUS_OK,
)

from .execution_storage_failover import (
    ExecutionStorageFailover,
    STATUS_FAILED_OVER,
    STATUS_PRIMARY,
    STATUS_UNAVAILABLE,
)

from .execution_storage_failover_error import (
    ExecutionStorageFailoverError,
)


class ExecutionStorageFailoverService:
    """
    Switches a volume's runtime storage access to a verified replica
    when its primary target becomes unavailable or corrupt.

    Composes with:
    - an existing storage replication service (anything exposing
      `replicas(volume_id) -> tuple of objects with .replica_id,
      .target, and .status`, matching
      ExecutionStorageReplicationService), used to confirm a target
      has a SYNCED replica before it can be selected
    - an existing storage integrity service (anything exposing
      `check_replica(replica_id) -> object with .status`, matching
      ExecutionStorageIntegrityService), used to confirm a target's
      replica is not CORRUPT before it can be selected

    Behavior:
    - register() records a volume's primary and backup targets, in
      priority order, and immediately performs an initial selection
    - execute() re-evaluates a volume's selection from scratch: the
      primary, then each backup in order, is tried until one with a
      SYNCED, verified (non-CORRUPT) replica is found
    - A volume fails over to UNAVAILABLE, with no selected_target,
      only when every configured target is unavailable or corrupt
    - select() and status() simply read the volume's last-computed
      selection without re-evaluating targets

    Selection is always recomputed from the full ordered target list,
    never from whatever was previously selected, so the same target
    health always yields the same selection.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, replica_service, integrity_service):
        self._replica_service = replica_service
        self._integrity_service = integrity_service
        self._configs_by_volume = {}
        self._states_by_volume = {}
        self._lock = RLock()

    def register(self, volume_id: str, targets) -> ExecutionStorageFailover:
        """
        Record volume_id's primary and backup targets and perform an
        initial selection.

        Args:
            volume_id: The volume to configure
            targets: An ordered, non-empty sequence of unique target
                IDs; the first is the primary, the rest are backups
                tried in the given order

        Raises:
            ExecutionStorageFailoverError: If volume_id is None or
                blank, or targets is empty or contains a blank or
                duplicate entry
        """

        self._validate_text(volume_id, "volume ID")

        if targets is None:
            raise ExecutionStorageFailoverError("Cannot register a volume with a None targets sequence.")

        ordered = list(targets)

        if not ordered:
            raise ExecutionStorageFailoverError("Cannot register a volume with an empty targets sequence.")

        for target in ordered:
            if not isinstance(target, str) or not target.strip():
                raise ExecutionStorageFailoverError("Cannot register a volume with a blank target.")

        if len(set(ordered)) != len(ordered):
            raise ExecutionStorageFailoverError("Cannot register a volume with duplicate targets.")

        with self._lock:
            existing = self._configs_by_volume.get(volume_id)
            failover_id = existing["failover_id"] if existing is not None else str(uuid4())

            self._configs_by_volume[volume_id] = {
                "failover_id": failover_id,
                "primary": ordered[0],
                "backups": tuple(ordered[1:]),
            }

            return self._execute_locked(volume_id)

    def execute(self, volume_id: str) -> ExecutionStorageFailover:
        """
        Re-evaluate volume_id's target selection from scratch.

        Raises:
            ExecutionStorageFailoverError: If volume_id is None or
                blank, or no targets are registered for it
        """

        self._validate_text(volume_id, "volume ID")

        with self._lock:
            self._require_registered(volume_id)

            return self._execute_locked(volume_id)

    def select(self, volume_id: str):
        """
        The target currently serving volume_id, or None if it has
        failed over completely.

        Raises:
            ExecutionStorageFailoverError: If volume_id is None or
                blank, or no targets are registered for it
        """

        return self._resolve(volume_id).selected_target

    def status(self, volume_id: str) -> str:
        """
        The current status of volume_id's failover configuration.

        Raises:
            ExecutionStorageFailoverError: If volume_id is None or
                blank, or no targets are registered for it
        """

        return self._resolve(volume_id).status

    def _execute_locked(self, volume_id: str) -> ExecutionStorageFailover:
        config = self._configs_by_volume[volume_id]
        candidates = (config["primary"],) + config["backups"]

        selected = next(
            (target for target in candidates if self._is_valid(volume_id, target)), None
        )

        if selected is None:
            status = STATUS_UNAVAILABLE
        elif selected == config["primary"]:
            status = STATUS_PRIMARY
        else:
            status = STATUS_FAILED_OVER

        failover = ExecutionStorageFailover(
            failover_id=config["failover_id"],
            volume_id=volume_id,
            primary_target=config["primary"],
            backup_targets=config["backups"],
            selected_target=selected,
            status=status,
        )

        self._states_by_volume[volume_id] = failover

        return failover

    def _is_valid(self, volume_id: str, target: str) -> bool:
        replica = self._find_replica(volume_id, target)

        if replica is None or replica.status != STATUS_SYNCED:
            return False

        try:
            check = self._integrity_service.check_replica(replica.replica_id)
        except Exception:
            return False

        return check.status == STATUS_OK

    def _find_replica(self, volume_id: str, target: str):
        try:
            replicas = self._replica_service.replicas(volume_id)
        except Exception:
            return None

        return next((replica for replica in replicas if replica.target == target), None)

    def _require_registered(self, volume_id: str) -> None:
        if volume_id not in self._configs_by_volume:
            raise ExecutionStorageFailoverError(f"No targets are registered for volume ID {volume_id!r}.")

    def _resolve(self, volume_id: str) -> ExecutionStorageFailover:
        self._validate_text(volume_id, "volume ID")

        with self._lock:
            self._require_registered(volume_id)

            return self._states_by_volume[volume_id]

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageFailoverError(f"Cannot use an empty or blank {field_name}.")
