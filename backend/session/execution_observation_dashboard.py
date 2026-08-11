from dataclasses import (
    dataclass,
    field,
)

from typing import Any

from uuid import uuid4

from .execution_observation_dashboard_error import (
    ExecutionObservationDashboardError,
)


@dataclass(frozen=True)
class ExecutionObservationDashboard:
    """
    Immutable snapshot of a dashboard aggregating a set of execution
    sessions' observation metrics, traces, and errors into a single,
    dashboard-ready summary.

    The dashboard is a value object only. It performs no aggregation
    of its own; creating a dashboard, refreshing its summary,
    reading it, and deleting the dashboard is the responsibility of
    an execution observation dashboard service.

    Attributes:
        dashboard_id: The dashboard's unique identifier
        name: A human-readable label for the dashboard
        session_ids: The distinct execution sessions this dashboard
            aggregates, in the order they were given at creation
        metrics: The dashboard's last-refreshed aggregated summary,
            covering metrics, traces, and errors; empty until the
            dashboard is first refreshed
    """

    name: str

    session_ids: tuple

    dashboard_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    metrics: dict[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self):
        self._require_text(self.dashboard_id, "dashboard ID")
        self._require_text(self.name, "name")

        if self.session_ids is None:
            raise ExecutionObservationDashboardError(
                "Cannot build an execution observation dashboard with a None session_ids."
            )

        session_id_list = list(self.session_ids)

        if not session_id_list:
            raise ExecutionObservationDashboardError(
                "Cannot build an execution observation dashboard with an empty session_ids."
            )

        for session_id in session_id_list:
            self._require_text(session_id, "session ID")

        if len(set(session_id_list)) != len(session_id_list):
            raise ExecutionObservationDashboardError(
                "Cannot build an execution observation dashboard with duplicate session IDs."
            )

        object.__setattr__(self, "session_ids", tuple(session_id_list))

        if not isinstance(self.metrics, dict):
            raise ExecutionObservationDashboardError(
                "Cannot build an execution observation dashboard with a non-dict metrics."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationDashboardError(
                f"Cannot build an execution observation dashboard with an empty or blank {field_name}."
            )
