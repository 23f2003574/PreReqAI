from datetime import datetime, timezone
from threading import RLock

from ..tool_execution import RUNNING, STATUSES, LLMToolExecution
from .models import (
    ATTEMPTS_METRIC,
    ATTEMPTS_UNIT,
    DURATION_METRIC,
    DURATION_UNIT,
    InvalidToolMetricError,
    LLMToolExecutionMetrics,
    UnknownToolMetricError,
)


class LLMToolMetricsService:
    """Measures finished tool executions (Commit #12).

    No parallel observability framework: the two conventions this codebase
    already has are both followed rather than replaced.

    Structurally it is LLMUsageService, the LLM layer's own telemetry
    service -- record() turns something that happened into a frozen record
    with a generated id and a recorded_at, keeps an append-only list plus a
    per-scope index, and offers grouped readers over it (there, total() and
    by_model(); here, aggregate()).

    For emission it defers to ExecutionMetricsService, the repository's
    metrics recorder. Rather than wrap it -- it is bound to runtimes and
    confirms a runtime exists before accepting a sample -- this service
    accepts any sink with its signature, record(scope_id, name, value,
    unit), and emits duration and attempt samples through it, named and
    united as ExecutionMetric expects. Supply an ExecutionMetricsService and
    tool samples land in the existing mechanism; supply nothing and metrics
    are still recorded here.

    There is no logging call anywhere in this service, because there is no
    logging call anywhere in this repository -- telemetry here means
    structured records, not log lines.

    On secrets: exclusion is structural. LLMToolExecutionMetrics has no
    field for arguments, output, or error text, so there is nothing to
    redact and no way for a payload to reach a metric. Durations, counts, a
    status and a tool name are all that is kept.
    """

    def __init__(self, retry_service=None, metrics_sink=None):
        """
        Args:
            retry_service: Commit #11's service. Consulted for how many
                attempts a logical call took; without it, an execution
                counts as a single attempt
            metrics_sink: Anything matching ExecutionMetricsService.record
                (scope_id, name, value, unit). Samples are emitted through
                it when supplied
        """
        self._retry_service = retry_service
        self._metrics_sink = metrics_sink
        self._records = []
        self._by_execution = {}
        self._by_tool = {}
        self._counter = 0
        self._lock = RLock()

    # -- recording ---------------------------------------------------------

    def _attempts_for(self, execution_id: str) -> int:
        """How many attempts the logical call took, per Commit #11."""
        if self._retry_service is None:
            return 1
        return self._retry_service.attempts(execution_id) or 1

    def record(self, execution) -> LLMToolExecutionMetrics:
        """Measure one finished execution.

        Refuses an execution that has not finished: a RUNNING call has no
        duration yet, and recording one would put a number in the record
        that is not a measurement of anything.
        """
        if not isinstance(execution, LLMToolExecution):
            raise InvalidToolMetricError(
                f"Cannot measure something that is not an LLMToolExecution: {execution!r}."
            )

        if execution.status == RUNNING or execution.completed_at is None:
            raise InvalidToolMetricError(
                f"Cannot measure execution {execution.execution_id!r}: it has not "
                "finished."
            )

        if execution.status not in STATUSES:
            raise InvalidToolMetricError(
                f"Cannot measure execution {execution.execution_id!r}: unknown status "
                f"{execution.status!r}."
            )

        duration = (execution.completed_at - execution.started_at).total_seconds()
        if duration < 0:
            raise InvalidToolMetricError(
                f"Cannot measure execution {execution.execution_id!r}: it completed "
                "before it started."
            )

        with self._lock:
            self._counter += 1
            metrics = LLMToolExecutionMetrics(
                metric_id=f"tool-metric-{self._counter}",
                execution_id=execution.execution_id,
                duration=duration,
                attempts=self._attempts_for(execution.execution_id),
                status=execution.status,
                tool_name=execution.tool_name,
                recorded_at=datetime.now(timezone.utc),
            )

            self._records.append(metrics)
            self._by_execution[metrics.execution_id] = metrics
            self._by_tool.setdefault(metrics.tool_name, []).append(metrics)

        self._emit(metrics)
        return metrics

    def _emit(self, metrics: LLMToolExecutionMetrics):
        """Push samples into the existing metrics mechanism, if one is wired."""
        if self._metrics_sink is None:
            return
        self._metrics_sink.record(
            metrics.tool_name, DURATION_METRIC, metrics.duration_ms, DURATION_UNIT
        )
        self._metrics_sink.record(
            metrics.tool_name, ATTEMPTS_METRIC, float(metrics.attempts), ATTEMPTS_UNIT
        )

    # -- reads -------------------------------------------------------------

    def get(self, execution_id: str) -> LLMToolExecutionMetrics:
        with self._lock:
            try:
                return self._by_execution[execution_id]
            except KeyError:
                raise UnknownToolMetricError(execution_id)

    def all(self, tool_name: str = None) -> tuple:
        """Every measurement, for one tool or across all of them, in order."""
        with self._lock:
            if tool_name is None:
                return tuple(self._records)
            return tuple(self._by_tool.get(tool_name, []))

    def aggregate(self, tool_name: str = None) -> dict:
        """Summary statistics for one tool, or across every tool if omitted.

        Returns zeroed totals rather than raising for a tool with nothing
        recorded, so a caller charting many tools does not have to special-
        case the quiet ones.
        """
        samples = self.all(tool_name)

        if not samples:
            return {
                "tool_name": tool_name,
                "executions": 0,
                "by_status": {},
                "total_duration": 0.0,
                "mean_duration": 0.0,
                "min_duration": 0.0,
                "max_duration": 0.0,
                "total_attempts": 0,
                "mean_attempts": 0.0,
                "retried_executions": 0,
            }

        durations = [sample.duration for sample in samples]
        attempts = [sample.attempts for sample in samples]

        by_status = {}
        for sample in samples:
            by_status[sample.status] = by_status.get(sample.status, 0) + 1

        return {
            "tool_name": tool_name,
            "executions": len(samples),
            "by_status": by_status,
            "total_duration": sum(durations),
            # Mean, as ExecutionMetricsService.aggregate computes it.
            "mean_duration": sum(durations) / len(durations),
            "min_duration": min(durations),
            "max_duration": max(durations),
            "total_attempts": sum(attempts),
            "mean_attempts": sum(attempts) / len(attempts),
            "retried_executions": sum(1 for count in attempts if count > 1),
        }
