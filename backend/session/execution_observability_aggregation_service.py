from datetime import (
    datetime,
    timezone,
)

from .execution_observability_summary import (
    ExecutionObservabilitySummary,
)

from .execution_observability_summary_error import (
    ExecutionObservabilitySummaryError,
)


class ExecutionObservabilityAggregationService:
    """
    Aggregates a runtime's previously recorded metrics and events
    into runtime-level observability summaries.

    Composes with existing observability services (duck-typed to what
    each already exposes):
        metrics_service: all(runtime_id) -> tuple of objects with
            .name, .value, .unit (ExecutionMetricsService)
        event_service: history(runtime_id) -> tuple of objects with
            .event_type, .severity (ExecutionEventService)

    The service performs no recording of its own or mutation of
    either composed service; every method here only reads what has
    already been recorded elsewhere.

    Behavior:
    - metrics() computes, per metric name, the mean value, its unit,
      and the sample count across every metric recorded for a runtime
    - events() counts a runtime's recorded events by event_type and
      by severity
    - errors() counts a runtime's recorded events of ERROR severity
    - generate() combines metrics(), events(), and errors() into a
      single summary
    - compare() reports the per-metric, per-event-count, and
      error_count differences between two summaries
    - A runtime with no recorded metrics or events produces empty
      aggregates rather than raising
    - Every method is a pure function of the currently recorded data:
      calling it again without any new metric or event recorded in
      between always produces the same result
    """

    def __init__(self, metrics_service, event_service):
        self._metrics_service = metrics_service
        self._event_service = event_service

    def generate(self, runtime_id: str) -> ExecutionObservabilitySummary:
        """
        Compute a fresh observability summary for runtime_id.

        Raises:
            ExecutionObservabilitySummaryError: If runtime_id is None
                or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        return ExecutionObservabilitySummary(
            runtime_id=runtime_id,
            metrics=self.metrics(runtime_id),
            event_counts=self.events(runtime_id),
            error_count=self.errors(runtime_id),
            generated_at=datetime.now(timezone.utc),
        )

    def metrics(self, runtime_id: str) -> dict:
        """
        Per metric name, the mean value, unit, and sample count
        across every metric recorded for runtime_id.

        Raises:
            ExecutionObservabilitySummaryError: If runtime_id is None
                or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        grouped = {}

        for metric in self._metrics_service.all(runtime_id):
            grouped.setdefault(metric.name, []).append(metric)

        summary = {}

        for name, samples in grouped.items():
            values = [sample.value for sample in samples]

            summary[name] = {
                "mean": sum(values) / len(values),
                "unit": samples[-1].unit,
                "count": len(values),
            }

        return summary

    def events(self, runtime_id: str) -> dict:
        """
        runtime_id's recorded event counts, grouped by event_type and
        by severity.

        Raises:
            ExecutionObservabilitySummaryError: If runtime_id is None
                or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        by_type = {}
        by_severity = {}

        for event in self._event_service.history(runtime_id):
            by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
            by_severity[event.severity] = by_severity.get(event.severity, 0) + 1

        return {"by_type": by_type, "by_severity": by_severity}

    def errors(self, runtime_id: str) -> int:
        """
        The number of ERROR-severity events recorded for runtime_id.

        Raises:
            ExecutionObservabilitySummaryError: If runtime_id is None
                or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        return sum(
            1 for event in self._event_service.history(runtime_id) if event.severity == "ERROR"
        )

    def compare(
        self, summary_a: ExecutionObservabilitySummary, summary_b: ExecutionObservabilitySummary
    ) -> dict:
        """
        The per-metric, per-event-count, and error_count differences
        between summary_a and summary_b (b relative to a).

        Raises:
            ExecutionObservabilitySummaryError: If summary_a or
                summary_b is not an ExecutionObservabilitySummary
        """

        if not isinstance(summary_a, ExecutionObservabilitySummary) or not isinstance(
            summary_b, ExecutionObservabilitySummary
        ):
            raise ExecutionObservabilitySummaryError(
                "Cannot compare objects that are not both execution observability summaries."
            )

        return {
            "runtime_a": summary_a.runtime_id,
            "runtime_b": summary_b.runtime_id,
            "metrics": self._diff_metrics(summary_a.metrics, summary_b.metrics),
            "event_counts": {
                "by_type": self._diff_counts(
                    summary_a.event_counts.get("by_type", {}),
                    summary_b.event_counts.get("by_type", {}),
                ),
                "by_severity": self._diff_counts(
                    summary_a.event_counts.get("by_severity", {}),
                    summary_b.event_counts.get("by_severity", {}),
                ),
            },
            "error_count": {
                "a": summary_a.error_count,
                "b": summary_b.error_count,
                "delta": summary_b.error_count - summary_a.error_count,
            },
        }

    @staticmethod
    def _diff_metrics(metrics_a: dict, metrics_b: dict) -> dict:
        diff = {}

        for name in sorted(set(metrics_a) | set(metrics_b)):
            entry_a = metrics_a.get(name)
            entry_b = metrics_b.get(name)

            mean_a = entry_a["mean"] if entry_a is not None else None
            mean_b = entry_b["mean"] if entry_b is not None else None

            diff[name] = {
                "a": mean_a,
                "b": mean_b,
                "unit": (entry_b or entry_a)["unit"],
                "delta": (mean_b - mean_a) if mean_a is not None and mean_b is not None else None,
            }

        return diff

    @staticmethod
    def _diff_counts(counts_a: dict, counts_b: dict) -> dict:
        diff = {}

        for key in sorted(set(counts_a) | set(counts_b)):
            count_a = counts_a.get(key, 0)
            count_b = counts_b.get(key, 0)

            diff[key] = {"a": count_a, "b": count_b, "delta": count_b - count_a}

        return diff

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilitySummaryError(f"Cannot use an empty or blank {field_name}.")
