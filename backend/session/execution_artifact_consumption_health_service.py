from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from .execution_artifact_consumption_health import (
    ExecutionArtifactConsumptionHealth,
)

from .execution_artifact_consumption_health_error import (
    ExecutionArtifactConsumptionHealthError,
)

_DEFAULT_STALE_AFTER = timedelta(minutes=30)


class ExecutionArtifactConsumptionHealthService:
    """
    Reports consumption-session health by combining an existing
    execution artifact consumption lease service, execution artifact
    consumption validation service, and each session's own tracked
    activity, so stale or failing artifact usage can be detected.

    The service's responsibility is health reporting only. It never
    mutates a consumption session, a lease, or a validation result.

    Behavior:
    - check() is fully read-only: it never records activity, so
      repeatedly checking a session that is never refresh()'d
      eventually reports it STALE
    - refresh() is the only way a session's last_activity advances; it
      records the current time as its most recent activity and
      returns the freshly recomputed health
    - invalid_artifacts combines artifacts that fail validation with
      artifacts whose most recently acquired lease has expired
      (whether or not cleanup() has recorded that yet), deduplicated
      and in that order
    - status is UNHEALTHY whenever invalid_artifacts is non-empty,
      otherwise STALE once last_activity is older than the configured
      staleness threshold, otherwise HEALTHY
    - stale() only considers sessions that have been refresh()'d at
      least once, in the order they were first refreshed
    - healthy(consumer) checks every one of a consumer's currently
      ACTIVE consumption sessions and returns the ones found HEALTHY,
      in that order

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_artifact_consumption_service,
        execution_artifact_consumption_lease_service,
        execution_artifact_consumption_validation_service,
        stale_after: timedelta = _DEFAULT_STALE_AFTER,
    ):
        """
        Args:
            execution_artifact_consumption_service: The service used
                to resolve a consumption session's status, consumer,
                and start time, and to list a consumer's active
                sessions. Any object exposing `get(consumption_id)`
                (returning an object with `.started_at`) and
                `active(consumer)`, raising if a session is unknown,
                is accepted
            execution_artifact_consumption_lease_service: The service
                used to resolve a consumption session's leases. Any
                object exposing `for_consumption(consumption_id)`
                (returning objects with `.artifact_id`, `.status`,
                and `.expires_at`) is accepted
            execution_artifact_consumption_validation_service: The
                service used to resolve a consumption session's
                current validation violations. Any object exposing
                `invalid(consumption_id)` (returning objects with
                `.artifact_id`) is accepted
            stale_after: How long a session may go without refresh()
                before it is considered STALE
        """

        if not isinstance(stale_after, timedelta):
            raise ExecutionArtifactConsumptionHealthError("Cannot use a non-timedelta stale_after.")

        self._execution_artifact_consumption_service = execution_artifact_consumption_service
        self._execution_artifact_consumption_lease_service = execution_artifact_consumption_lease_service
        self._execution_artifact_consumption_validation_service = execution_artifact_consumption_validation_service
        self._stale_after = stale_after
        self._last_activity_by_consumption = {}
        self._refreshed_ids_in_order = []
        self._lock = RLock()

    def check(self, consumption_id: str) -> ExecutionArtifactConsumptionHealth:
        """
        Compute a consumption session's current health, without
        recording any activity.

        Raises:
            ExecutionArtifactConsumptionHealthError: If consumption_id
                is None or blank, or no consumption session is known
                under it
        """

        self._validate_id(consumption_id, "consumption ID")

        with self._lock:
            session = self._resolve_session(consumption_id)

            return self._compute(consumption_id, session)

    def refresh(self, consumption_id: str) -> ExecutionArtifactConsumptionHealth:
        """
        Record a consumption session as active right now, and return
        its freshly recomputed health.

        Raises:
            ExecutionArtifactConsumptionHealthError: If consumption_id
                is None or blank, or no consumption session is known
                under it
        """

        self._validate_id(consumption_id, "consumption ID")

        with self._lock:
            session = self._resolve_session(consumption_id)

            if consumption_id not in self._last_activity_by_consumption:
                self._refreshed_ids_in_order.append(consumption_id)

            self._last_activity_by_consumption[consumption_id] = datetime.now(timezone.utc)

            return self._compute(consumption_id, session)

    def stale(self) -> list:
        """
        List the health of every refresh()'d session currently found
        STALE, in the order they were first refreshed.
        """

        with self._lock:
            results = []

            for consumption_id in self._refreshed_ids_in_order:
                try:
                    session = self._resolve_session(consumption_id)
                except ExecutionArtifactConsumptionHealthError:
                    continue

                health = self._compute(consumption_id, session)

                if health.status == "STALE":
                    results.append(health)

            return results

    def healthy(self, consumer: str) -> list:
        """
        List the health of every one of a consumer's currently ACTIVE
        consumption sessions found HEALTHY, in the order
        active() returns them.

        Raises:
            ExecutionArtifactConsumptionHealthError: If consumer is
                None or blank
        """

        self._validate_id(consumer, "consumer")

        with self._lock:
            results = []

            for session in self._execution_artifact_consumption_service.active(consumer):
                health = self._compute(session.consumption_id, session)

                if health.status == "HEALTHY":
                    results.append(health)

            return results

    def _compute(self, consumption_id: str, session) -> ExecutionArtifactConsumptionHealth:
        last_activity = self._last_activity_by_consumption.get(consumption_id, session.started_at)

        invalid_artifact_ids = []

        try:
            violations = self._execution_artifact_consumption_validation_service.invalid(consumption_id)
        except Exception:
            violations = []

        for violation in violations:
            if violation.artifact_id not in invalid_artifact_ids:
                invalid_artifact_ids.append(violation.artifact_id)

        latest_lease_by_artifact = {}

        for lease in self._execution_artifact_consumption_lease_service.for_consumption(consumption_id):
            latest_lease_by_artifact[lease.artifact_id] = lease

        for artifact_id, lease in latest_lease_by_artifact.items():
            if self._is_lease_expired(lease) and artifact_id not in invalid_artifact_ids:
                invalid_artifact_ids.append(artifact_id)

        if invalid_artifact_ids:
            status = "UNHEALTHY"
        elif datetime.now(timezone.utc) - last_activity > self._stale_after:
            status = "STALE"
        else:
            status = "HEALTHY"

        return ExecutionArtifactConsumptionHealth(
            consumption_id=consumption_id,
            status=status,
            last_activity=last_activity,
            invalid_artifacts=tuple(invalid_artifact_ids),
        )

    @staticmethod
    def _is_lease_expired(lease) -> bool:
        return lease.status == "EXPIRED" or (
            lease.status == "ACTIVE" and lease.expires_at <= datetime.now(timezone.utc)
        )

    def _resolve_session(self, consumption_id: str):
        try:
            return self._execution_artifact_consumption_service.get(consumption_id)
        except Exception as error:
            raise ExecutionArtifactConsumptionHealthError(
                f"No consumption session is known under consumption ID {consumption_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionHealthError(f"Cannot use an empty or blank {field_name}.")
