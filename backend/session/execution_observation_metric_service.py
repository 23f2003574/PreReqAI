from threading import (
    RLock,
)

from .execution_observation_metric_error import (
    ExecutionObservationMetricError,
)

from .execution_observation_metric import (
    ExecutionObservationMetric,
)


class ExecutionObservationMetricService:
    """
    Aggregates execution observation events into runtime metrics,
    kept isolated per execution session.

    The service's responsibility is metric bookkeeping and
    aggregation only. It does not derive metric values itself;
    execution observation events are assumed to already exist, and a
    caller decides what value to record() against a session.

    Behavior:
    - record() is append-only: no method updates or removes a
      metric once recorded
    - metrics() always returns a session's recorded metrics in
      chronological (recorded_at) order
    - aggregate() computes the mean value across a session's
      recorded metrics of a given metric_type; the result depends
      only on the set of recorded values, never on recording order
    - A metric recorded against one session never appears in another
      session's metrics() or aggregate()

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._metrics_by_session = {}
        self._lock = RLock()

    def record(self, session_id: str, metric_type: str, value: float) -> ExecutionObservationMetric:
        """
        Build and append a new metric.

        Raises:
            ExecutionObservationMetricError: If session_id or
                metric_type is None or blank, or value is not
                numeric
        """

        metric = ExecutionObservationMetric(
            session_id=session_id,
            metric_type=metric_type,
            value=value,
        )

        with self._lock:
            self._metrics_by_session.setdefault(session_id, []).append(metric)

            return metric

    def metrics(self, session_id: str) -> list:
        """
        List every recorded metric for a session, oldest to newest.

        Raises:
            ExecutionObservationMetricError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            recorded = list(self._metrics_by_session.get(session_id, []))

            return sorted(recorded, key=lambda metric: metric.recorded_at)

    def aggregate(self, session_id: str, metric_type: str) -> float:
        """
        Compute the mean value across a session's recorded metrics of
        a given metric_type.

        Raises:
            ExecutionObservationMetricError: If session_id or
                metric_type is None or blank, or the session has no
                recorded metric of that type
        """

        self._validate_id(metric_type, "metric type")

        values = [metric.value for metric in self.metrics(session_id) if metric.metric_type == metric_type]

        if not values:
            raise ExecutionObservationMetricError(
                f"Session ID {session_id!r} has no recorded metric of metric_type {metric_type!r}."
            )

        return sum(values) / len(values)

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationMetricError(f"Cannot use an empty or blank {field_name}.")
