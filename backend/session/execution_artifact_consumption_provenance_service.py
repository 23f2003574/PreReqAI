from threading import (
    RLock,
)

from .execution_artifact_consumption_provenance import (
    ExecutionArtifactConsumptionProvenance,
)

from .execution_artifact_consumption_provenance_error import (
    ExecutionArtifactConsumptionProvenanceError,
)


class ExecutionArtifactConsumptionProvenanceService:
    """
    Records an append-only trail of which consumer, session, and
    exact artifact version participated in each consumption
    operation, using an existing execution artifact consumption
    service to confirm a session is active and resolve its consumer,
    and an existing execution artifact version service to capture the
    exact version consumed.

    The service's responsibility is provenance bookkeeping only. It
    never mutates a consumption session or an artifact version, and
    never edits or removes a record once written.

    Behavior:
    - record() only records against an ACTIVE consumption session
    - Every record captures the artifact's current latest version at
      the moment of recording, permanently
    - Records are append-only: once written, a record is never
      edited or removed
    - history(), artifact_history(), and latest() all preserve
      chronological (recording) order

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_consumption_service, execution_artifact_version_service):
        """
        Args:
            execution_artifact_consumption_service: The service used
                to confirm a consumption session is ACTIVE and to
                resolve its consumer. Any object exposing
                `get(consumption_id)` (returning an object with
                `.status` and `.consumer`), raising if the session is
                unknown, is accepted
            execution_artifact_version_service: The service used to
                resolve the exact version of an artifact being
                consumed. Any object exposing `latest(artifact_id)`,
                raising if the artifact has no version, is accepted
        """

        self._execution_artifact_consumption_service = execution_artifact_consumption_service
        self._execution_artifact_version_service = execution_artifact_version_service
        self._provenance_ids_by_consumption = {}
        self._provenance_ids_by_artifact = {}
        self._provenance_by_id = {}
        self._lock = RLock()

    def record(self, consumption_id: str, artifact_id: str) -> ExecutionArtifactConsumptionProvenance:
        """
        Record a consumption operation against an active session.

        Raises:
            ExecutionArtifactConsumptionProvenanceError: If
                consumption_id or artifact_id is None or blank, no
                consumption session is known under consumption_id, it
                is not ACTIVE, or artifact_id has no version yet
        """

        self._validate_id(consumption_id, "consumption ID")
        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            session = self._ensure_active_consumption(consumption_id)
            version = self._latest_version(artifact_id)

            record = ExecutionArtifactConsumptionProvenance(
                consumption_id=consumption_id,
                artifact_id=artifact_id,
                version=version,
                consumer=session.consumer,
            )

            self._provenance_by_id[record.provenance_id] = record
            self._provenance_ids_by_consumption.setdefault(consumption_id, []).append(record.provenance_id)
            self._provenance_ids_by_artifact.setdefault(artifact_id, []).append(record.provenance_id)

            return record

    def history(self, consumption_id: str) -> list:
        """
        List every provenance record for a consumption session, in
        the order they were recorded.

        Raises:
            ExecutionArtifactConsumptionProvenanceError: If
                consumption_id is None or blank
        """

        self._validate_id(consumption_id, "consumption ID")

        with self._lock:
            return [
                self._provenance_by_id[provenance_id]
                for provenance_id in self._provenance_ids_by_consumption.get(consumption_id, [])
            ]

    def artifact_history(self, artifact_id: str) -> list:
        """
        List every provenance record for an artifact, across every
        consumption session, in the order they were recorded.

        Raises:
            ExecutionArtifactConsumptionProvenanceError: If
                artifact_id is None or blank
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return [
                self._provenance_by_id[provenance_id]
                for provenance_id in self._provenance_ids_by_artifact.get(artifact_id, [])
            ]

    def latest(self, consumption_id: str) -> ExecutionArtifactConsumptionProvenance:
        """
        Look up a consumption session's most recently recorded
        provenance record.

        Raises:
            ExecutionArtifactConsumptionProvenanceError: If
                consumption_id is None or blank, or it has no
                provenance records yet
        """

        self._validate_id(consumption_id, "consumption ID")

        with self._lock:
            provenance_ids = self._provenance_ids_by_consumption.get(consumption_id, [])

            if not provenance_ids:
                raise ExecutionArtifactConsumptionProvenanceError(
                    f"Consumption ID {consumption_id!r} has no provenance records."
                )

            return self._provenance_by_id[provenance_ids[-1]]

    def _ensure_active_consumption(self, consumption_id: str):
        try:
            session = self._execution_artifact_consumption_service.get(consumption_id)
        except Exception as error:
            raise ExecutionArtifactConsumptionProvenanceError(
                f"No consumption session is known under consumption ID {consumption_id!r}."
            ) from error

        if session.status != "ACTIVE":
            raise ExecutionArtifactConsumptionProvenanceError(
                f"Cannot record provenance for consumption ID {consumption_id!r}: it is {session.status}, "
                "not ACTIVE."
            )

        return session

    def _latest_version(self, artifact_id: str) -> int:
        try:
            return self._execution_artifact_version_service.latest(artifact_id).version
        except Exception as error:
            raise ExecutionArtifactConsumptionProvenanceError(
                f"Artifact ID {artifact_id!r} has no version to record."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionProvenanceError(f"Cannot use an empty or blank {field_name}.")
