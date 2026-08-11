from threading import (
    RLock,
)

from .execution_observation_health_error import (
    ExecutionObservationHealthError,
)

from .execution_observation_health import (
    ExecutionObservationHealth,
)


class ExecutionObservationHealthService:
    """
    Detects unhealthy execution sessions by combining a session's
    recorded metrics, traces, errors, and active alerts into a
    single overall status.

    The service's responsibility is health evaluation and check
    bookkeeping only. It never records observation data itself;
    observation metrics, traces, errors, and alerts are assumed to
    already exist in the injected services, and this service only
    reads from them.

    Behavior:
    - check() is read-only with respect to the injected services: it
      only calls their read methods, never anything that records or
      mutates observation data
    - A session is UNHEALTHY if it has any currently active alert;
      otherwise it is DEGRADED if it has any FAILED trace or any
      recorded error; otherwise it is HEALTHY
    - reasons are built in a fixed, deterministic order: active
      alerts first, then failed traces, then errors, each group in
      the order the underlying service already returns them
    - check() appends a new record to the session's history; it
      never overwrites or removes a prior check
    - unhealthy() and healthy() report each known session's
      most-recently-checked status, in the order that session was
      first checked

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, metric_service, trace_service, error_service, alert_service):
        """
        Args:
            metric_service: The service used to confirm session_id is
                known. Any object exposing `metrics(session_id)`,
                raising if session_id is unknown to it, is accepted
            trace_service: The service used to read a session's
                recorded traces. Any object exposing
                `history(session_id)`, raising if session_id is
                unknown to it, is accepted
            error_service: The service used to read a session's
                recorded errors. Any object exposing
                `history(session_id)`, raising if session_id is
                unknown to it, is accepted
            alert_service: The service used to read a session's
                currently active alerts. Any object exposing
                `active(session_id)`, raising if session_id is
                unknown to it, is accepted
        """

        self._metric_service = metric_service
        self._trace_service = trace_service
        self._error_service = error_service
        self._alert_service = alert_service
        self._history_by_session = {}
        self._session_order = []
        self._lock = RLock()

    def check(self, session_id: str) -> ExecutionObservationHealth:
        """
        Run a new health check for a session, combining its currently
        recorded metrics, traces, errors, and active alerts.

        Raises:
            ExecutionObservationHealthError: If session_id is None or
                blank, or it is not known to every injected
                observation service
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_known(session_id)

            active_alerts = self._alert_service.active(session_id)
            failed_traces = [trace for trace in self._trace_service.history(session_id) if trace.status == "FAILED"]
            errors = self._error_service.history(session_id)

            reasons = (
                [
                    f"Alert {alert.alert_id} ({alert.severity}) is active for metric type {alert.metric_type!r}."
                    for alert in active_alerts
                ]
                + [f"Trace {trace.trace_id} for stage {trace.stage_id!r} failed." for trace in failed_traces]
                + [f"Error {error.error_id} ({error.error_type}): {error.message}" for error in errors]
            )

            if active_alerts:
                status = "UNHEALTHY"
            elif failed_traces or errors:
                status = "DEGRADED"
            else:
                status = "HEALTHY"

            health = ExecutionObservationHealth(session_id=session_id, status=status, reasons=tuple(reasons))

            if session_id not in self._history_by_session:
                self._session_order.append(session_id)

            self._history_by_session.setdefault(session_id, []).append(health)

            return health

    def unhealthy(self) -> list:
        """
        List every known session whose most recent check is
        UNHEALTHY, in the order each session was first checked.
        """

        return self._latest_by_status("UNHEALTHY")

    def healthy(self) -> list:
        """
        List every known session whose most recent check is HEALTHY,
        in the order each session was first checked.
        """

        return self._latest_by_status("HEALTHY")

    def history(self, session_id: str) -> list:
        """
        List every check recorded for a session, oldest to newest.

        Raises:
            ExecutionObservationHealthError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return list(self._history_by_session.get(session_id, []))

    def _latest_by_status(self, status: str) -> list:
        with self._lock:
            return [
                self._history_by_session[session_id][-1]
                for session_id in self._session_order
                if self._history_by_session[session_id][-1].status == status
            ]

    def _ensure_known(self, session_id: str) -> None:
        try:
            self._metric_service.metrics(session_id)
            self._trace_service.history(session_id)
            self._error_service.history(session_id)
            self._alert_service.active(session_id)
        except Exception as error:
            raise ExecutionObservationHealthError(
                f"Session ID {session_id!r} is not known to observation services."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationHealthError(f"Cannot use an empty or blank {field_name}.")
