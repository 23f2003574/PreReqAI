from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_observation_dashboard_error import (
    ExecutionObservationDashboardError,
)

from .execution_observation_dashboard import (
    ExecutionObservationDashboard,
)


class ExecutionObservationDashboardService:
    """
    Exposes a set of execution sessions' observation metrics, traces,
    and errors as dashboard-ready aggregated summaries.

    The service's responsibility is dashboard bookkeeping and
    aggregation only. It never records observation data itself;
    observation metrics, traces, and errors are assumed to already
    exist in the injected services, and this service only reads from
    them.

    Behavior:
    - create() rejects any session_id not known to every injected
      observation service
    - refresh() is read-only with respect to the injected services:
      it only calls their read methods (metrics()/history()), never
      anything that records or mutates observation data, and stores
      the resulting aggregation on the dashboard itself
    - summary() returns a dashboard's last-refreshed aggregation as
      of the most recent refresh(); it does not recompute it
    - A dashboard's session_ids are kept in the order given to
      create(), and aggregation only ever draws from those sessions

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, metric_service, trace_service, error_service):
        """
        Args:
            metric_service: The service used to read a session's
                recorded metrics. Any object exposing
                `metrics(session_id)`, raising if session_id is
                unknown to it, is accepted
            trace_service: The service used to read a session's
                recorded traces. Any object exposing
                `history(session_id)`, raising if session_id is
                unknown to it, is accepted
            error_service: The service used to read a session's
                recorded errors. Any object exposing
                `history(session_id)`, raising if session_id is
                unknown to it, is accepted
        """

        self._metric_service = metric_service
        self._trace_service = trace_service
        self._error_service = error_service
        self._dashboards_by_id = {}
        self._lock = RLock()

    def create(self, name: str, session_ids) -> ExecutionObservationDashboard:
        """
        Create a new dashboard aggregating a set of execution
        sessions.

        Raises:
            ExecutionObservationDashboardError: If name is None or
                blank, session_ids is None, empty, or contains a
                blank or duplicate session ID, or a session ID is not
                known to every injected observation service
        """

        with self._lock:
            dashboard = ExecutionObservationDashboard(name=name, session_ids=session_ids)

            for session_id in dashboard.session_ids:
                self._ensure_known(session_id)

            self._dashboards_by_id[dashboard.dashboard_id] = dashboard

            return dashboard

    def refresh(self, dashboard_id: str) -> ExecutionObservationDashboard:
        """
        Recompute a dashboard's aggregated summary from its sessions'
        currently recorded metrics, traces, and errors.

        Raises:
            ExecutionObservationDashboardError: If dashboard_id is
                None or blank, or no dashboard is known under it
        """

        self._validate_id(dashboard_id, "dashboard ID")

        with self._lock:
            dashboard = self._resolve(dashboard_id)

            updated = replace(dashboard, metrics=self._aggregate(dashboard.session_ids))
            self._dashboards_by_id[dashboard_id] = updated

            return updated

    def summary(self, dashboard_id: str) -> dict:
        """
        Read a dashboard's last-refreshed aggregated summary.

        Raises:
            ExecutionObservationDashboardError: If dashboard_id is
                None or blank, or no dashboard is known under it
        """

        self._validate_id(dashboard_id, "dashboard ID")

        with self._lock:
            return self._resolve(dashboard_id).metrics

    def delete(self, dashboard_id: str) -> ExecutionObservationDashboard:
        """
        Permanently remove a dashboard.

        Raises:
            ExecutionObservationDashboardError: If dashboard_id is
                None or blank, or no dashboard is known under it
        """

        self._validate_id(dashboard_id, "dashboard ID")

        with self._lock:
            dashboard = self._resolve(dashboard_id)
            del self._dashboards_by_id[dashboard_id]

            return dashboard

    def _aggregate(self, session_ids) -> dict:
        values_by_metric_type = {}
        traces_total = 0
        traces_active = 0
        traces_succeeded = 0
        traces_failed = 0
        durations = []
        errors_total = 0
        errors_by_type = {}

        for session_id in session_ids:
            for metric in self._metric_service.metrics(session_id):
                values_by_metric_type.setdefault(metric.metric_type, []).append(metric.value)

            for trace in self._trace_service.history(session_id):
                traces_total += 1

                if trace.status == "ACTIVE":
                    traces_active += 1
                    continue

                if trace.status == "SUCCEEDED":
                    traces_succeeded += 1
                elif trace.status == "FAILED":
                    traces_failed += 1

                durations.append((trace.finished_at - trace.started_at).total_seconds())

            for error in self._error_service.history(session_id):
                errors_total += 1
                errors_by_type[error.error_type] = errors_by_type.get(error.error_type, 0) + 1

        return {
            "sessions": list(session_ids),
            "metrics": {
                metric_type: sum(values) / len(values) for metric_type, values in values_by_metric_type.items()
            },
            "traces": {
                "total": traces_total,
                "active": traces_active,
                "succeeded": traces_succeeded,
                "failed": traces_failed,
                "average_duration_seconds": (sum(durations) / len(durations)) if durations else None,
            },
            "errors": {
                "total": errors_total,
                "by_type": errors_by_type,
            },
        }

    def _ensure_known(self, session_id: str) -> None:
        try:
            self._metric_service.metrics(session_id)
            self._trace_service.history(session_id)
            self._error_service.history(session_id)
        except Exception as error:
            raise ExecutionObservationDashboardError(
                f"Session ID {session_id!r} is not known to observation services."
            ) from error

    def _resolve(self, dashboard_id: str) -> ExecutionObservationDashboard:
        dashboard = self._dashboards_by_id.get(dashboard_id)

        if dashboard is None:
            raise ExecutionObservationDashboardError(f"No dashboard is known under dashboard ID {dashboard_id!r}.")

        return dashboard

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationDashboardError(f"Cannot use an empty or blank {field_name}.")
