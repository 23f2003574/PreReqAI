import dataclasses
import time
from datetime import datetime, timedelta, timezone

import pytest

from backend.llm.retry import TransientLLMError
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import (
    CANCELLED,
    DENIED,
    FAILED,
    LLMToolExecutionService,
    REJECTED,
    RUNNING,
    SUCCEEDED,
    TIMED_OUT,
    LLMToolExecution,
)
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_metrics import (
    ATTEMPTS_METRIC,
    DURATION_METRIC,
    InvalidToolMetricError,
    LLMToolExecutionMetrics,
    LLMToolMetricsService,
    UnknownToolMetricError,
)
from backend.llm.tool_permissions import (
    ANY_SUBJECT,
    LLMToolPermissionPolicy,
    LLMToolPermissionService,
)
from backend.llm.tool_retry import LLMToolRetryPolicy, LLMToolRetryService
from backend.llm.tools import LLMToolRegistryService

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)

SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_id": {"type": "string"},
        "api_key": {"type": "string"},
    },
    "required": ["analysis_id"],
}


class RecordingSink:
    """Matches ExecutionMetricsService.record(scope_id, name, value, unit)."""

    def __init__(self):
        self.samples = []

    def record(self, scope_id, name, value, unit):
        self.samples.append((scope_id, name, value, unit))
        return (scope_id, name, value, unit)


class FlakyTool:
    def __init__(self, failures=0, delay=0.0):
        self.failures = failures
        self.delay = delay
        self.calls = 0

    def __call__(self, analysis_id, api_key=None):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.calls <= self.failures:
            raise TransientLLMError("upstream is briefly unavailable")
        return {"analysis_id": analysis_id, "cell_count": 3}


def execution(status=SUCCEEDED, seconds=0.25, tool_name="summarize_notebook_analysis", **over):
    fields = {
        "execution_id": "tool-execution-1",
        "plan_id": "tool-plan-1",
        "tool_name": tool_name,
        "status": status,
        "result": {"cell_count": 3} if status == SUCCEEDED else None,
        "error": None if status == SUCCEEDED else f"{status} for a reason",
        "started_at": NOW,
        "completed_at": NOW + timedelta(seconds=seconds),
    }
    fields.update(over)
    return LLMToolExecution(**fields)


def build(tool=None, allow=True, policy=None):
    registry = LLMToolRegistryService()
    registry.register(
        "summarize_notebook_analysis", "Summarize a notebook analysis.", SUMMARIZE_SCHEMA
    )
    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    if allow:
        permissions.register(
            LLMToolPermissionPolicy(
                policy_id="allow-1",
                tool_name="summarize_notebook_analysis",
                subject=ANY_SUBJECT,
                allowed=True,
            )
        )
    tool = tool if tool is not None else FlakyTool()
    execution_service = LLMToolExecutionService(registry, permissions)
    execution_service.bind("summarize_notebook_analysis", tool)
    control = LLMToolExecutionControlService(execution_service)
    retry = LLMToolRetryService(
        control,
        execution_service,
        policy or LLMToolRetryPolicy(max_attempts=3, backoff=0.0),
        sleeper=lambda seconds: None,
    )
    sink = RecordingSink()
    metrics = LLMToolMetricsService(retry, sink)
    return {
        "registry": registry,
        "invocation": invocation,
        "execution": execution_service,
        "control": control,
        "retry": retry,
        "metrics": metrics,
        "sink": sink,
        "tool": tool,
    }


def plan_for(stack, **arguments):
    return stack["invocation"].plan(
        {
            "name": "summarize_notebook_analysis",
            "arguments": arguments or {"analysis_id": "analysis-1"},
        }
    )


@pytest.fixture(autouse=True)
def _shutdown_pools():
    created = []
    original = LLMToolExecutionControlService.__init__

    def tracking_init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        created.append(self)

    LLMToolExecutionControlService.__init__ = tracking_init
    try:
        yield
    finally:
        LLMToolExecutionControlService.__init__ = original
        for service in created:
            service.shutdown(wait=False)


# ---------------------------------------------------------------------------
# recording
# ---------------------------------------------------------------------------


def test_successful_execution_metrics():
    metrics = LLMToolMetricsService()

    record = metrics.record(execution(seconds=0.25))

    assert record.execution_id == "tool-execution-1"
    assert record.tool_name == "summarize_notebook_analysis"
    assert record.status == SUCCEEDED
    assert record.duration == pytest.approx(0.25)
    assert record.duration_ms == pytest.approx(250.0)
    assert record.attempts == 1
    assert record.metric_id == "tool-metric-1"
    assert record.recorded_at is not None
    assert metrics.get("tool-execution-1") == record


def test_failed_execution_metrics():
    metrics = LLMToolMetricsService()

    record = metrics.record(execution(status=FAILED, seconds=1.5))

    assert record.status == FAILED
    assert record.duration == pytest.approx(1.5)
    assert record.attempts == 1


@pytest.mark.parametrize("status", [SUCCEEDED, FAILED, DENIED, REJECTED, TIMED_OUT, CANCELLED])
def test_every_execution_state_is_supported(status):
    metrics = LLMToolMetricsService()

    record = metrics.record(execution(status=status, seconds=0.1))

    assert record.status == status
    assert record.duration == pytest.approx(0.1)


def test_a_running_execution_cannot_be_measured():
    """A call still in flight has no duration to record."""
    metrics = LLMToolMetricsService()

    with pytest.raises(InvalidToolMetricError, match="not finished"):
        metrics.record(execution(status=RUNNING, completed_at=None))


def test_malformed_input_is_refused():
    metrics = LLMToolMetricsService()

    with pytest.raises(InvalidToolMetricError):
        metrics.record({"execution_id": "e-1"})

    with pytest.raises(InvalidToolMetricError, match="unknown status"):
        metrics.record(execution(status="MAYBE"))

    with pytest.raises(InvalidToolMetricError, match="before it started"):
        metrics.record(execution(completed_at=NOW - timedelta(seconds=1)))

    with pytest.raises(UnknownToolMetricError):
        metrics.get("does-not-exist")


def test_records_are_immutable():
    metrics = LLMToolMetricsService()
    record = metrics.record(execution())

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.duration = 99.0


# ---------------------------------------------------------------------------
# real executions, end to end
# ---------------------------------------------------------------------------


def test_metrics_for_a_real_successful_execution():
    stack = build()
    record = stack["execution"].execute(plan_for(stack), "user:ada")

    measured = stack["metrics"].record(record)

    assert measured.status == SUCCEEDED
    assert measured.duration >= 0.0
    assert measured.tool_name == "summarize_notebook_analysis"


def test_metrics_for_a_denied_execution():
    stack = build(allow=False)
    record = stack["execution"].execute(plan_for(stack), "user:ada")

    measured = stack["metrics"].record(record)

    assert measured.status == DENIED
    assert measured.attempts == 1


def test_retry_attempt_count_comes_from_commit_11():
    stack = build(tool=FlakyTool(failures=2))
    record = stack["retry"].execute(plan_for(stack), "user:ada")
    assert record.status == SUCCEEDED

    measured = stack["metrics"].record(record)

    assert measured.attempts == 3
    assert stack["retry"].attempts(record.execution_id) == 3


def test_attempts_default_to_one_without_a_retry_service():
    stack = build(tool=FlakyTool(failures=2))
    record = stack["retry"].execute(plan_for(stack), "user:ada")
    standalone = LLMToolMetricsService()

    assert standalone.record(record).attempts == 1


def test_metrics_for_a_timed_out_execution():
    stack = build(
        tool=FlakyTool(delay=0.4),
        policy=LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
    )
    record = stack["control"].execute_with_timeout(plan_for(stack), "user:ada", timeout=0.05)
    assert record.status == TIMED_OUT

    measured = stack["metrics"].record(record)

    assert measured.status == TIMED_OUT
    assert measured.duration > 0.0
    time.sleep(0.6)


def test_metrics_for_a_cancelled_execution():
    import threading

    stack = build(tool=FlakyTool(delay=0.3))
    control = stack["control"]
    threading.Thread(
        target=lambda: control.execute_with_timeout(plan_for(stack), "user:ada", timeout=5)
    ).start()
    time.sleep(0.05)
    cancelled = control.cancel("tool-control-1")

    measured = stack["metrics"].record(cancelled)

    assert measured.status == CANCELLED
    assert measured.duration > 0.0
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# emission into the existing metrics mechanism
# ---------------------------------------------------------------------------


def test_samples_are_emitted_to_the_existing_metrics_sink():
    """The sink matches ExecutionMetricsService.record(scope, name, value, unit)."""
    sink = RecordingSink()
    metrics = LLMToolMetricsService(metrics_sink=sink)

    metrics.record(execution(seconds=0.25))

    assert sink.samples == [
        ("summarize_notebook_analysis", DURATION_METRIC, 250.0, "ms"),
        ("summarize_notebook_analysis", ATTEMPTS_METRIC, 1.0, "count"),
    ]


def test_samples_land_in_the_real_execution_metrics_service():
    """Not just a duck-typed stub: the actual repository metrics recorder
    accepts these samples and aggregates them."""
    from backend.session.execution_metrics_service import ExecutionMetricsService

    class KnownScopes:
        """Minimal runtime service: ExecutionMetricsService only asks whether
        a scope exists before accepting a sample."""

        def status(self, runtime_id):
            return "RUNNING"

    sink = ExecutionMetricsService(KnownScopes())
    metrics = LLMToolMetricsService(metrics_sink=sink)

    metrics.record(execution(execution_id="e-1", seconds=0.2))
    metrics.record(execution(execution_id="e-2", seconds=0.4))

    durations = sink.history("summarize_notebook_analysis", DURATION_METRIC)
    assert [sample.value for sample in durations] == [200.0, 400.0]
    assert [sample.unit for sample in durations] == ["ms", "ms"]
    assert sink.aggregate("summarize_notebook_analysis", DURATION_METRIC) == pytest.approx(300.0)
    assert sink.aggregate("summarize_notebook_analysis", ATTEMPTS_METRIC) == pytest.approx(1.0)


def test_metrics_are_still_recorded_without_a_sink():
    metrics = LLMToolMetricsService()

    record = metrics.record(execution())

    assert metrics.get(record.execution_id) == record


def test_emitted_samples_carry_the_retry_attempt_count():
    stack = build(tool=FlakyTool(failures=1))
    record = stack["retry"].execute(plan_for(stack), "user:ada")

    stack["metrics"].record(record)

    attempts_sample = [s for s in stack["sink"].samples if s[1] == ATTEMPTS_METRIC]
    assert attempts_sample[0][2] == 2.0


# ---------------------------------------------------------------------------
# aggregation
# ---------------------------------------------------------------------------


def test_aggregation_for_one_tool():
    metrics = LLMToolMetricsService()
    metrics.record(execution(execution_id="e-1", seconds=0.2))
    metrics.record(execution(execution_id="e-2", seconds=0.4, status=FAILED))
    metrics.record(execution(execution_id="e-3", seconds=0.6))

    summary = metrics.aggregate("summarize_notebook_analysis")

    assert summary["executions"] == 3
    assert summary["by_status"] == {SUCCEEDED: 2, FAILED: 1}
    assert summary["total_duration"] == pytest.approx(1.2)
    assert summary["mean_duration"] == pytest.approx(0.4)
    assert summary["min_duration"] == pytest.approx(0.2)
    assert summary["max_duration"] == pytest.approx(0.6)
    assert summary["total_attempts"] == 3
    assert summary["mean_attempts"] == pytest.approx(1.0)
    assert summary["retried_executions"] == 0


def test_aggregation_isolates_tools():
    metrics = LLMToolMetricsService()
    metrics.record(execution(execution_id="e-1", seconds=0.2))
    metrics.record(execution(execution_id="e-2", seconds=1.0, tool_name="analyze_notebook"))

    first = metrics.aggregate("summarize_notebook_analysis")
    second = metrics.aggregate("analyze_notebook")

    assert first["executions"] == 1
    assert first["mean_duration"] == pytest.approx(0.2)
    assert second["executions"] == 1
    assert second["mean_duration"] == pytest.approx(1.0)

    across = metrics.aggregate()
    assert across["executions"] == 2
    assert across["total_duration"] == pytest.approx(1.2)


def test_aggregation_of_a_quiet_tool_is_zeroed_not_an_error():
    metrics = LLMToolMetricsService()

    summary = metrics.aggregate("never_called")

    assert summary["executions"] == 0
    assert summary["by_status"] == {}
    assert summary["mean_duration"] == 0.0
    assert summary["total_attempts"] == 0


def test_aggregation_counts_retried_executions():
    stack = build(tool=FlakyTool(failures=2))
    retried = stack["retry"].execute(plan_for(stack), "user:ada")
    stack["metrics"].record(retried)
    stack["metrics"].record(execution(execution_id="e-clean", seconds=0.1))

    summary = stack["metrics"].aggregate("summarize_notebook_analysis")

    assert summary["executions"] == 2
    assert summary["retried_executions"] == 1
    assert summary["total_attempts"] == 4  # 3 + 1


def test_all_lists_measurements_in_order():
    metrics = LLMToolMetricsService()
    first = metrics.record(execution(execution_id="e-1"))
    other = metrics.record(execution(execution_id="e-2", tool_name="analyze_notebook"))
    second = metrics.record(execution(execution_id="e-3"))

    assert metrics.all() == (first, other, second)
    assert metrics.all("summarize_notebook_analysis") == (first, second)


# ---------------------------------------------------------------------------
# secret exclusion
# ---------------------------------------------------------------------------


def test_secret_exclusion_is_structural():
    """There is no field for arguments, output, or error -- nothing to leak."""
    stack = build()
    plan = plan_for(stack, analysis_id="analysis-1", api_key="sk-abcdefghijklmnopqrst")
    record = stack["execution"].execute(plan, "user:ada")

    measured = stack["metrics"].record(record)

    for absent in ("arguments", "output", "result", "error", "tool_call", "subject"):
        assert not hasattr(measured, absent)

    stored = repr(dataclasses.asdict(measured))
    assert "sk-abcdefghijklmnopqrst" not in stored
    assert "api_key" not in stored


def test_a_failing_tools_error_text_never_reaches_a_metric():
    stack = build()

    def leaky(analysis_id, api_key=None):
        raise RuntimeError("upstream rejected api_key=sk-abcdefghijklmnop")

    stack["execution"].bind("summarize_notebook_analysis", leaky)
    record = stack["execution"].execute(plan_for(stack), "user:ada")
    assert record.status == FAILED

    measured = stack["metrics"].record(record)

    assert measured.status == FAILED
    assert "sk-" not in repr(dataclasses.asdict(measured))


def test_emitted_samples_carry_only_numbers():
    stack = build()
    plan = plan_for(stack, analysis_id="analysis-1", api_key="sk-abcdefghijklmnopqrst")
    stack["metrics"].record(stack["execution"].execute(plan, "user:ada"))

    for scope_id, name, value, unit in stack["sink"].samples:
        assert isinstance(value, float)
        assert "sk-" not in scope_id
        assert "sk-" not in name
        assert "sk-" not in unit


def test_the_metrics_service_executes_nothing():
    metrics = LLMToolMetricsService()

    for attr in ("invoke", "call", "execute", "run", "dispatch", "bind"):
        assert not hasattr(metrics, attr)


def test_the_metrics_model_is_a_plain_value_object():
    record = LLMToolExecutionMetrics(
        metric_id="tool-metric-1",
        execution_id="tool-execution-1",
        duration=0.5,
        attempts=2,
        status=SUCCEEDED,
        tool_name="summarize_notebook_analysis",
        recorded_at=NOW,
    )

    assert record.duration_ms == pytest.approx(500.0)
