from threading import (
    RLock,
)

from .execution_metric import (
    ExecutionMetric,
)

from .execution_metric_error import (
    ExecutionMetricError,
)


class ExecutionMetricsService:
    """
    Records structured runtime metrics for execution performance and
    resource usage, kept isolated per runtime.

    Composes with an existing runtime service (anything exposing
    `status(runtime_id) -> str`, matching
    ExecutionRuntimeStartupService), used to confirm a runtime exists
    before a metric can be recorded against it.

    Behavior:
    - record() is append-only: no method updates or removes a metric
      once recorded; every sample is preserved in the order it was
      recorded
    - latest() reports a runtime's most recently recorded metric for
      a given name, or None if it has never been recorded
    - history() reports every metric recorded for a runtime and name,
      oldest to newest
    - all() reports every metric recorded for a runtime, across all
      names, oldest to newest
    - aggregate() computes the mean value across a runtime's recorded
      metrics of a given name
    - A metric recorded against one runtime never appears in another
      runtime's latest(), history(), or aggregate()

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, runtime_service):
        self._runtime_service = runtime_service
        self._metrics_by_runtime = {}
        self._lock = RLock()

    def record(self, runtime_id: str, name: str, value: float, unit: str) -> ExecutionMetric:
        """
        Record a new metric sample for runtime_id.

        Raises:
            ExecutionMetricError: If runtime_id, name, or unit is
                None or blank, value is not numeric, or runtime_id is
                unknown
        """

        self._validate_text(runtime_id, "runtime ID")
        self._confirm_runtime_exists(runtime_id)

        metric = ExecutionMetric(
            runtime_id=runtime_id,
            name=name,
            value=value,
            unit=unit,
        )

        with self._lock:
            self._metrics_by_runtime.setdefault(runtime_id, []).append(metric)

            return metric

    def latest(self, runtime_id: str, name: str):
        """
        The most recently recorded metric for runtime_id and name, or
        None if it has never been recorded.

        Raises:
            ExecutionMetricError: If runtime_id or name is None or
                blank
        """

        samples = self.history(runtime_id, name)

        return samples[-1] if samples else None

    def history(self, runtime_id: str, name: str) -> tuple:
        """
        Every metric recorded for runtime_id and name, oldest to
        newest.

        Raises:
            ExecutionMetricError: If runtime_id or name is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(name, "name")

        with self._lock:
            recorded = list(self._metrics_by_runtime.get(runtime_id, []))

        matching = [metric for metric in recorded if metric.name == name]

        return tuple(sorted(matching, key=lambda metric: metric.recorded_at))

    def all(self, runtime_id: str) -> tuple:
        """
        Every metric recorded for runtime_id, across all names,
        oldest to newest.

        Raises:
            ExecutionMetricError: If runtime_id is None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            recorded = list(self._metrics_by_runtime.get(runtime_id, []))

        return tuple(sorted(recorded, key=lambda metric: metric.recorded_at))

    def aggregate(self, runtime_id: str, name: str) -> float:
        """
        Compute the mean value across runtime_id's recorded metrics
        of a given name.

        Raises:
            ExecutionMetricError: If runtime_id or name is None or
                blank, or no metric of that name has been recorded
                for runtime_id
        """

        samples = self.history(runtime_id, name)

        if not samples:
            raise ExecutionMetricError(
                f"Runtime ID {runtime_id!r} has no recorded metric named {name!r}."
            )

        values = [metric.value for metric in samples]

        return sum(values) / len(values)

    def _confirm_runtime_exists(self, runtime_id: str) -> None:
        try:
            self._runtime_service.status(runtime_id)
        except Exception as error:
            raise ExecutionMetricError(
                f"Cannot record a metric for runtime ID {runtime_id!r}: it is unknown."
            ) from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionMetricError(f"Cannot use an empty or blank {field_name}.")
