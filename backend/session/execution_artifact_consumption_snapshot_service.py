from threading import (
    RLock,
)

from .execution_artifact_consumption_snapshot import (
    ExecutionArtifactConsumptionSnapshot,
)

from .execution_artifact_consumption_snapshot_error import (
    ExecutionArtifactConsumptionSnapshotError,
)


class ExecutionArtifactConsumptionSnapshotService:
    """
    Captures the exact artifact versions an active consumption
    session holds at a single point in time, so that state can later
    be restored or audited, using an existing execution artifact
    consumption service to resolve a session's currently tracked
    artifacts and an existing execution artifact version service to
    resolve each one's current latest version.

    The service's responsibility is snapshot bookkeeping only. It
    does not track consumption sessions or artifact versions
    themselves, and it never mutates either.

    Behavior:
    - create() only snapshots a consumption session that is currently
      ACTIVE; an unknown or non-ACTIVE session is rejected
    - Every snapshot is immutable once created: later changes to a
      session's tracked artifacts, or new versions created for them,
      never alter a snapshot already taken
    - restore() re-resolves each artifact/version pair a snapshot
      recorded, exactly as recorded, not whatever is currently latest
    - latest() returns a consumption session's most recently created
      snapshot; history() returns every snapshot for it, oldest to
      newest

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_consumption_service, execution_artifact_version_service):
        """
        Args:
            execution_artifact_consumption_service: The service used
                to resolve a consumption session's status and
                currently tracked artifacts. Any object exposing
                `get(consumption_id)` (returning an object with
                `.status` and `.artifact_ids`), raising if the
                session is unknown, is accepted
            execution_artifact_version_service: The service used to
                resolve an artifact's latest version at snapshot
                time, and to re-resolve an exact version at restore
                time. Any object exposing `latest(artifact_id)` and
                `get(artifact_id, version)`, each raising if
                unresolvable, is accepted
        """

        self._execution_artifact_consumption_service = execution_artifact_consumption_service
        self._execution_artifact_version_service = execution_artifact_version_service
        self._snapshots_by_id = {}
        self._snapshot_ids_by_consumption = {}
        self._lock = RLock()

    def create(self, consumption_id: str) -> ExecutionArtifactConsumptionSnapshot:
        """
        Capture a new snapshot of an active consumption session's
        currently tracked artifacts, each at its current latest
        version.

        Raises:
            ExecutionArtifactConsumptionSnapshotError: If
                consumption_id is None or blank, no consumption
                session is known under it, it is not ACTIVE, or any
                of its tracked artifacts has no version yet
        """

        self._validate_id(consumption_id, "consumption ID")

        with self._lock:
            session = self._ensure_active_consumption(consumption_id)

            artifact_versions = {}

            for artifact_id in session.artifact_ids:
                artifact_versions[artifact_id] = self._latest_version(artifact_id)

            snapshot = ExecutionArtifactConsumptionSnapshot(
                consumption_id=consumption_id,
                artifact_versions=artifact_versions,
            )

            self._snapshots_by_id[snapshot.snapshot_id] = snapshot
            self._snapshot_ids_by_consumption.setdefault(consumption_id, []).append(snapshot.snapshot_id)

            return snapshot

    def restore(self, snapshot_id: str) -> dict:
        """
        Re-resolve every artifact/version pair a snapshot recorded,
        exactly as recorded.

        Raises:
            ExecutionArtifactConsumptionSnapshotError: If snapshot_id
                is None or blank, no snapshot is known under it, or
                any of its recorded artifact/version pairs can no
                longer be resolved
        """

        self._validate_id(snapshot_id, "snapshot ID")

        with self._lock:
            snapshot = self._resolve(snapshot_id)

            resolved = {}

            for artifact_id, version in snapshot.artifact_versions.items():
                try:
                    resolved[artifact_id] = self._execution_artifact_version_service.get(artifact_id, version)
                except Exception as error:
                    raise ExecutionArtifactConsumptionSnapshotError(
                        f"Cannot restore snapshot ID {snapshot_id!r}: version {version!r} of artifact ID "
                        f"{artifact_id!r} is no longer resolvable."
                    ) from error

            return resolved

    def latest(self, consumption_id: str) -> ExecutionArtifactConsumptionSnapshot:
        """
        Look up a consumption session's most recently created
        snapshot.

        Raises:
            ExecutionArtifactConsumptionSnapshotError: If
                consumption_id is None or blank, or it has no
                snapshots yet
        """

        self._validate_id(consumption_id, "consumption ID")

        with self._lock:
            snapshot_ids = self._snapshot_ids_by_consumption.get(consumption_id, [])

            if not snapshot_ids:
                raise ExecutionArtifactConsumptionSnapshotError(
                    f"Consumption ID {consumption_id!r} has no snapshots."
                )

            return self._snapshots_by_id[snapshot_ids[-1]]

    def history(self, consumption_id: str) -> list:
        """
        List every snapshot captured for a consumption session,
        oldest to newest.

        Raises:
            ExecutionArtifactConsumptionSnapshotError: If
                consumption_id is None or blank
        """

        self._validate_id(consumption_id, "consumption ID")

        with self._lock:
            return [
                self._snapshots_by_id[snapshot_id]
                for snapshot_id in self._snapshot_ids_by_consumption.get(consumption_id, [])
            ]

    def _ensure_active_consumption(self, consumption_id: str):
        try:
            session = self._execution_artifact_consumption_service.get(consumption_id)
        except Exception as error:
            raise ExecutionArtifactConsumptionSnapshotError(
                f"No consumption session is known under consumption ID {consumption_id!r}."
            ) from error

        if session.status != "ACTIVE":
            raise ExecutionArtifactConsumptionSnapshotError(
                f"Cannot snapshot consumption ID {consumption_id!r}: it is {session.status}, not ACTIVE."
            )

        return session

    def _latest_version(self, artifact_id: str) -> int:
        try:
            return self._execution_artifact_version_service.latest(artifact_id).version
        except Exception as error:
            raise ExecutionArtifactConsumptionSnapshotError(
                f"Artifact ID {artifact_id!r} has no version to snapshot."
            ) from error

    def _resolve(self, snapshot_id: str) -> ExecutionArtifactConsumptionSnapshot:
        snapshot = self._snapshots_by_id.get(snapshot_id)

        if snapshot is None:
            raise ExecutionArtifactConsumptionSnapshotError(
                f"No snapshot is known under snapshot ID {snapshot_id!r}."
            )

        return snapshot

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionSnapshotError(f"Cannot use an empty or blank {field_name}.")
