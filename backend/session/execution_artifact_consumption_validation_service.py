from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_artifact_consumption_validation import (
    ExecutionArtifactConsumptionValidation,
)

from .execution_artifact_consumption_validation_error import (
    ExecutionArtifactConsumptionValidationError,
)


class ExecutionArtifactConsumptionValidationService:
    """
    Validates that every artifact a consumption session is actively
    tracking still exists, is accessible to the session's consumer,
    and satisfies its required version, using an existing execution
    artifact consumption service, execution artifact registry,
    execution artifact access service, execution artifact version
    service, and execution artifact consumption snapshot service to
    perform those checks.

    The service's responsibility is validation only. It never
    mutates a consumption session, an artifact, a permission, a
    version, or a snapshot.

    Behavior:
    - Checks run in a fixed order for every artifact: existence,
      access, version existence, then required version; the first
      failing check determines the recorded reason
    - An artifact's required version is whatever version its
      consumption session's most recent snapshot recorded for it; an
      artifact with no snapshot yet, or not present in the most
      recent one, has nothing required of it and passes this check
    - validate() and its per-artifact checks are stateless: each call
      recomputes fresh against current state, so the same session
      and snapshot state always yields the same, deterministically
      ordered result
    - validate_artifact() only checks an artifact currently tracked
      by the given consumption session; asking about an artifact it
      is not tracking is rejected outright, not reported as invalid
    - invalid() and report() are both derived from validate(),
      following the same order and never trigger side effects

    The service is:
    - Thread-safe: All reads are guarded by an internal lock
    """

    def __init__(
        self,
        execution_artifact_consumption_service,
        execution_artifact_service,
        execution_artifact_access_service,
        execution_artifact_version_service,
        execution_artifact_consumption_snapshot_service,
    ):
        """
        Args:
            execution_artifact_consumption_service: The service used
                to resolve a consumption session's consumer and
                currently tracked artifacts. Any object exposing
                `get(consumption_id)` (returning an object with
                `.consumer` and `.artifact_ids`), raising if the
                session is unknown, is accepted
            execution_artifact_service: The registry used to check an
                artifact's existence. Any object exposing
                `get(artifact_id)`, raising if the artifact is
                unknown, is accepted
            execution_artifact_access_service: The service used to
                check the session's consumer has READ access. Any
                object exposing `authorize(artifact_id, principal,
                operation)`, returning an object with an `.allowed`
                attribute, is accepted
            execution_artifact_version_service: The service used to
                check an artifact currently has a version at all. Any
                object exposing `latest(artifact_id)`, raising if the
                artifact has no version, is accepted
            execution_artifact_consumption_snapshot_service: The
                service used to resolve the required version an
                artifact was last pinned at. Any object exposing
                `latest(consumption_id)` (returning an object with
                `.artifact_versions`), raising if the session has no
                snapshot yet, is accepted
        """

        self._execution_artifact_consumption_service = execution_artifact_consumption_service
        self._execution_artifact_service = execution_artifact_service
        self._execution_artifact_access_service = execution_artifact_access_service
        self._execution_artifact_version_service = execution_artifact_version_service
        self._execution_artifact_consumption_snapshot_service = execution_artifact_consumption_snapshot_service
        self._lock = RLock()

    def validate(self, consumption_id: str) -> list:
        """
        Check every artifact a consumption session is currently
        tracking, in the order the session tracks them.

        Raises:
            ExecutionArtifactConsumptionValidationError: If
                consumption_id is None or blank, or no consumption
                session is known under it
        """

        self._validate_id(consumption_id, "consumption ID")

        with self._lock:
            session = self._resolve_session(consumption_id)

            return [
                self._check(consumption_id, artifact_id, session.consumer)
                for artifact_id in session.artifact_ids
            ]

    def validate_artifact(self, consumption_id: str, artifact_id: str) -> ExecutionArtifactConsumptionValidation:
        """
        Check a single artifact currently tracked by a consumption
        session.

        Raises:
            ExecutionArtifactConsumptionValidationError: If
                consumption_id or artifact_id is None or blank, no
                consumption session is known under consumption_id, or
                it is not currently tracking artifact_id
        """

        self._validate_id(consumption_id, "consumption ID")
        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            session = self._resolve_session(consumption_id)

            if artifact_id not in session.artifact_ids:
                raise ExecutionArtifactConsumptionValidationError(
                    f"Consumption ID {consumption_id!r} is not tracking artifact ID {artifact_id!r}."
                )

            return self._check(consumption_id, artifact_id, session.consumer)

    def invalid(self, consumption_id: str) -> list:
        """
        List only the failing checks from validate(), in the same
        order.

        Raises:
            ExecutionArtifactConsumptionValidationError: If
                consumption_id is None or blank, or no consumption
                session is known under it
        """

        return [validation for validation in self.validate(consumption_id) if not validation.valid]

    def report(self, consumption_id: str) -> dict:
        """
        Summarize a consumption session's current validation state.

        Raises:
            ExecutionArtifactConsumptionValidationError: If
                consumption_id is None or blank, or no consumption
                session is known under it
        """

        validations = self.validate(consumption_id)
        violations = [validation for validation in validations if not validation.valid]

        return {
            "consumption_id": consumption_id,
            "checked_at": datetime.now(timezone.utc),
            "total": len(validations),
            "valid_count": len(validations) - len(violations),
            "invalid_count": len(violations),
            "violations": violations,
        }

    def _check(self, consumption_id: str, artifact_id: str, consumer: str) -> ExecutionArtifactConsumptionValidation:
        try:
            self._execution_artifact_service.get(artifact_id)
        except Exception:
            return ExecutionArtifactConsumptionValidation(
                consumption_id=consumption_id,
                artifact_id=artifact_id,
                valid=False,
                reason=f"Artifact ID {artifact_id!r} does not exist.",
            )

        try:
            authorization = self._execution_artifact_access_service.authorize(artifact_id, consumer, "READ")
            allowed = authorization.allowed
        except Exception:
            allowed = False

        if not allowed:
            return ExecutionArtifactConsumptionValidation(
                consumption_id=consumption_id,
                artifact_id=artifact_id,
                valid=False,
                reason=f"Consumer {consumer!r} does not have READ access to artifact ID {artifact_id!r}.",
            )

        try:
            latest_version = self._execution_artifact_version_service.latest(artifact_id).version
        except Exception:
            return ExecutionArtifactConsumptionValidation(
                consumption_id=consumption_id,
                artifact_id=artifact_id,
                valid=False,
                reason=f"Artifact ID {artifact_id!r} has no version to satisfy the required version check.",
            )

        required_version = self._required_version(consumption_id, artifact_id)

        if required_version is not None and latest_version != required_version:
            return ExecutionArtifactConsumptionValidation(
                consumption_id=consumption_id,
                artifact_id=artifact_id,
                valid=False,
                reason=(
                    f"Artifact ID {artifact_id!r} is at version {latest_version}, but version "
                    f"{required_version} is required."
                ),
            )

        return ExecutionArtifactConsumptionValidation(
            consumption_id=consumption_id,
            artifact_id=artifact_id,
            valid=True,
            reason="Artifact exists, is accessible, and satisfies its required version.",
        )

    def _required_version(self, consumption_id: str, artifact_id: str):
        try:
            snapshot = self._execution_artifact_consumption_snapshot_service.latest(consumption_id)
        except Exception:
            return None

        return snapshot.artifact_versions.get(artifact_id)

    def _resolve_session(self, consumption_id: str):
        try:
            return self._execution_artifact_consumption_service.get(consumption_id)
        except Exception as error:
            raise ExecutionArtifactConsumptionValidationError(
                f"No consumption session is known under consumption ID {consumption_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionValidationError(f"Cannot use an empty or blank {field_name}.")
