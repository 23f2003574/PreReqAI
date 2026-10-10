from threading import (
    RLock,
)

from .execution_artifact_consumption_diff import (
    ExecutionArtifactConsumptionDiff,
)

from .execution_artifact_consumption_reconciliation_error import (
    ExecutionArtifactConsumptionReconciliationError,
)


class ExecutionArtifactConsumptionReconciliationService:
    """
    Reconciles a consumption session against a snapshot recorded for
    it, identifying which artifacts have been added, removed, or
    changed version since, using an existing execution artifact
    consumption service, execution artifact consumption snapshot
    service, and execution artifact version service.

    The service's responsibility is comparison and reconciliation
    only. It never mutates a snapshot, and only ever mutates a
    consumption session's tracked artifacts through apply().

    Behavior:
    - compare() is read-only: it never mutates the consumption
      session, the snapshot, or any artifact
    - A snapshot must belong to the consumption session it is
      compared against
    - added lists artifacts tracked now but absent from the snapshot;
      removed lists artifacts the snapshot recorded that are no
      longer tracked; changed lists artifacts tracked both now and by
      the snapshot whose current version differs from the recorded
      one
    - apply() only reconciles an ACTIVE session's tracked artifacts
      back to the snapshot's recorded set: added artifacts are
      dropped, removed artifacts are re-added; version changes are
      reported but never reverted, since versions are immutable
    - changes() computes compare() against a consumption session's
      most recently created snapshot

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_artifact_consumption_service,
        execution_artifact_consumption_snapshot_service,
        execution_artifact_version_service,
    ):
        """
        Args:
            execution_artifact_consumption_service: The service used
                to resolve a consumption session's status and
                currently tracked artifacts, and to reconcile them in
                apply(). Any object exposing `get(consumption_id)`
                (returning an object with `.status` and
                `.artifact_ids`), `add(consumption_id, artifact_id)`,
                and `remove(consumption_id, artifact_id)` is accepted
            execution_artifact_consumption_snapshot_service: The
                service used to resolve a consumption session's
                snapshots. Any object exposing `history(consumption_id)`
                (returning objects with `.snapshot_id` and
                `.artifact_versions`) and `latest(consumption_id)`,
                raising if the session has no snapshot yet, is
                accepted
            execution_artifact_version_service: The service used to
                resolve an artifact's current latest version. Any
                object exposing `latest(artifact_id)` is accepted
        """

        self._execution_artifact_consumption_service = execution_artifact_consumption_service
        self._execution_artifact_consumption_snapshot_service = execution_artifact_consumption_snapshot_service
        self._execution_artifact_version_service = execution_artifact_version_service
        self._lock = RLock()

    def compare(self, consumption_id: str, snapshot_id: str) -> ExecutionArtifactConsumptionDiff:
        """
        Compare a consumption session's currently tracked artifacts
        against a snapshot recorded for it.

        Raises:
            ExecutionArtifactConsumptionReconciliationError: If
                consumption_id or snapshot_id is None or blank, no
                consumption session is known under consumption_id, or
                no snapshot with snapshot_id belongs to it
        """

        self._validate_id(consumption_id, "consumption ID")
        self._validate_id(snapshot_id, "snapshot ID")

        with self._lock:
            session = self._resolve_session(consumption_id)
            snapshot = self._resolve_snapshot(consumption_id, snapshot_id)

            return self._diff(consumption_id, session, snapshot)

    def apply(self, consumption_id: str, snapshot_id: str) -> ExecutionArtifactConsumptionDiff:
        """
        Reconcile an active consumption session's tracked artifacts
        back to a snapshot's recorded set: artifacts the snapshot
        did not record are dropped, and artifacts it recorded but the
        session no longer tracks are re-added.

        Raises:
            ExecutionArtifactConsumptionReconciliationError: If
                consumption_id or snapshot_id is None or blank, no
                consumption session is known under consumption_id, it
                is not ACTIVE, or no snapshot with snapshot_id belongs
                to it
        """

        self._validate_id(consumption_id, "consumption ID")
        self._validate_id(snapshot_id, "snapshot ID")

        with self._lock:
            session = self._resolve_session(consumption_id)

            if session.status != "ACTIVE":
                raise ExecutionArtifactConsumptionReconciliationError(
                    f"Cannot apply reconciliation to consumption ID {consumption_id!r}: it is "
                    f"{session.status}, not ACTIVE."
                )

            snapshot = self._resolve_snapshot(consumption_id, snapshot_id)
            diff = self._diff(consumption_id, session, snapshot)

            for artifact_id in diff.added:
                self._execution_artifact_consumption_service.remove(consumption_id, artifact_id)

            for artifact_id in diff.removed:
                self._execution_artifact_consumption_service.add(consumption_id, artifact_id)

            return diff

    def changes(self, consumption_id: str) -> ExecutionArtifactConsumptionDiff:
        """
        Compare a consumption session against its most recently
        created snapshot.

        Raises:
            ExecutionArtifactConsumptionReconciliationError: If
                consumption_id is None or blank, no consumption
                session is known under it, or it has no snapshot yet
        """

        self._validate_id(consumption_id, "consumption ID")

        try:
            latest_snapshot = self._execution_artifact_consumption_snapshot_service.latest(consumption_id)
        except Exception as error:
            raise ExecutionArtifactConsumptionReconciliationError(
                f"Consumption ID {consumption_id!r} has no snapshot to compare against."
            ) from error

        return self.compare(consumption_id, latest_snapshot.snapshot_id)

    def _diff(self, consumption_id: str, session, snapshot) -> ExecutionArtifactConsumptionDiff:
        current_ids = set(session.artifact_ids)
        snapshot_ids = set(snapshot.artifact_versions.keys())

        added = [artifact_id for artifact_id in session.artifact_ids if artifact_id not in snapshot_ids]
        removed = [artifact_id for artifact_id in snapshot.artifact_versions if artifact_id not in current_ids]

        changed = {}

        for artifact_id in session.artifact_ids:
            if artifact_id not in snapshot_ids:
                continue

            recorded_version = snapshot.artifact_versions[artifact_id]

            try:
                current_version = self._execution_artifact_version_service.latest(artifact_id).version
            except Exception:
                continue

            if current_version != recorded_version:
                changed[artifact_id] = (recorded_version, current_version)

        return ExecutionArtifactConsumptionDiff(
            consumption_id=consumption_id,
            added=tuple(added),
            removed=tuple(removed),
            changed=changed,
        )

    def _resolve_session(self, consumption_id: str):
        try:
            return self._execution_artifact_consumption_service.get(consumption_id)
        except Exception as error:
            raise ExecutionArtifactConsumptionReconciliationError(
                f"No consumption session is known under consumption ID {consumption_id!r}."
            ) from error

    def _resolve_snapshot(self, consumption_id: str, snapshot_id: str):
        for snapshot in self._execution_artifact_consumption_snapshot_service.history(consumption_id):
            if snapshot.snapshot_id == snapshot_id:
                return snapshot

        raise ExecutionArtifactConsumptionReconciliationError(
            f"No snapshot ID {snapshot_id!r} is known for consumption ID {consumption_id!r}."
        )

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionReconciliationError(f"Cannot use an empty or blank {field_name}.")
