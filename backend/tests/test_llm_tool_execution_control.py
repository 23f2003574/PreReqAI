import threading
import time

import pytest

from backend.llm.tool_audit import LLMToolAuditService
from backend.llm.tool_control import (
    ExecutionAlreadyCompletedError,
    InvalidTimeoutError,
    LLMToolExecutionControlService,
    UnknownControlledExecutionError,
)
from backend.llm.tool_execution import (
    CANCELLED,
    DENIED,
    FAILED,
    LLMToolExecutionService,
    REJECTED,
    RUNNING,
    SUCCEEDED,
    TIMED_OUT,
)
from backend.llm.tool_idempotency import LLMToolIdempotencyService
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_permissions import (
    ANY_SUBJECT,
    LLMToolPermissionPolicy,
    LLMToolPermissionService,
)
from backend.llm.tool_results import LLMToolResultService
from backend.llm.tools import LLMToolRegistryService

SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {"analysis_id": {"type": "string"}},
    "required": ["analysis_id"],
}


class SlowTool:
    """A real handler whose duration and outcome the test controls."""

    def __init__(self, delay=0.0, fail_times=0):
        self.delay = delay
        self.fail_times = fail_times
        self.calls = 0
        self.released = threading.Event()

    def __call__(self, analysis_id):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.calls <= self.fail_times:
            raise RuntimeError("transient upstream failure")
        return {"analysis_id": analysis_id, "cell_count": 3}


def build(tool=None, allow=True, with_idempotency=False, with_audit=False):
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
    tool = tool or SlowTool()
    execution = LLMToolExecutionService(registry, permissions)
    execution.bind("summarize_notebook_analysis", tool)

    idempotency = (
        LLMToolIdempotencyService(execution, permissions) if with_idempotency else None
    )
    audit = LLMToolAuditService() if with_audit else None
    control = LLMToolExecutionControlService(execution, idempotency, audit)

    return {
        "registry": registry,
        "invocation": invocation,
        "permissions": permissions,
        "execution": execution,
        "idempotency": idempotency,
        "audit": audit,
        "control": control,
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
# normal completion
# ---------------------------------------------------------------------------


def test_normal_completion():
    stack = build()
    control = stack["control"]

    record = control.execute_with_timeout(plan_for(stack), "user:ada", timeout=5)

    assert record.status == SUCCEEDED
    assert record.result == {"analysis_id": "analysis-1", "cell_count": 3}
    assert record.error is None
    assert record.timeout_at is not None
    assert record.timeout_at > record.started_at
    assert record.cancelled_at is None
    assert stack["tool"].calls == 1


def test_status_is_reachable_by_both_identifiers():
    stack = build()
    control = stack["control"]

    record = control.execute_with_timeout(plan_for(stack), "user:ada", timeout=5)

    assert control.status(record.execution_id) == SUCCEEDED
    assert control.status("tool-control-1") == SUCCEEDED
    assert control.get("tool-control-1") == record


def test_gates_still_run_before_execution():
    """Validation and authorization are Commit #5's, unchanged."""
    denied_stack = build(allow=False)
    denied = denied_stack["control"].execute_with_timeout(
        plan_for(denied_stack), "user:ada", timeout=5
    )
    assert denied.status == DENIED
    assert denied_stack["tool"].calls == 0

    disabled_stack = build()
    plan = plan_for(disabled_stack)
    disabled_stack["registry"].disable("summarize_notebook_analysis")
    rejected = disabled_stack["control"].execute_with_timeout(plan, "user:ada", timeout=5)
    assert rejected.status == REJECTED
    assert disabled_stack["tool"].calls == 0


def test_a_failing_tool_is_still_reported_as_failed():
    stack = build(tool=SlowTool(fail_times=1))

    record = stack["control"].execute_with_timeout(plan_for(stack), "user:ada", timeout=5)

    assert record.status == FAILED
    assert "transient upstream failure" in record.error


@pytest.mark.parametrize("timeout", [0, -1, None, "5", True])
def test_a_non_positive_timeout_is_refused(timeout):
    stack = build()

    with pytest.raises(InvalidTimeoutError):
        stack["control"].execute_with_timeout(plan_for(stack), "user:ada", timeout)


def test_execute_with_timeout_rejects_a_non_plan():
    stack = build()

    with pytest.raises(TypeError):
        stack["control"].execute_with_timeout({"name": "x"}, "user:ada", timeout=5)


# ---------------------------------------------------------------------------
# timeout
# ---------------------------------------------------------------------------


def test_timeout_releases_the_caller_and_marks_the_record():
    stack = build(tool=SlowTool(delay=2.0))
    control = stack["control"]

    started = time.monotonic()
    record = control.execute_with_timeout(plan_for(stack), "user:ada", timeout=0.1)
    elapsed = time.monotonic() - started

    assert elapsed < 1.0  # the caller did not wait for the slow tool
    assert record.status == TIMED_OUT
    assert record.result is None
    assert "did not return before its deadline" in record.error
    assert record.timeout_at is not None
    assert record.completed_at is not None


def test_a_late_result_never_becomes_a_success():
    """The rule that matters most: a timed-out call is not retroactively
    reported as successful when its worker finally returns."""
    tool = SlowTool(delay=0.3)
    stack = build(tool=tool)
    control = stack["control"]

    record = control.execute_with_timeout(plan_for(stack), "user:ada", timeout=0.05)
    assert record.status == TIMED_OUT

    time.sleep(0.6)  # let the orphaned worker finish

    assert control.status(record.execution_id) == TIMED_OUT
    assert control.get(record.execution_id).result is None
    # The late result is accounted for, not silently dropped.
    orphaned = control.orphaned()
    assert len(orphaned) == 1
    assert orphaned[0].status == SUCCEEDED


def test_a_timed_out_execution_cannot_be_cancelled():
    stack = build(tool=SlowTool(delay=0.5))
    control = stack["control"]
    record = control.execute_with_timeout(plan_for(stack), "user:ada", timeout=0.05)

    with pytest.raises(ExecutionAlreadyCompletedError, match=TIMED_OUT):
        control.cancel(record.execution_id)


# ---------------------------------------------------------------------------
# cancellation
# ---------------------------------------------------------------------------


def test_cancellation_of_an_in_flight_execution():
    tool = SlowTool(delay=0.4)
    stack = build(tool=tool)
    control = stack["control"]
    outcome = {}

    def run():
        outcome["record"] = control.execute_with_timeout(
            plan_for(stack), "user:ada", timeout=5
        )

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.05)  # let it get in flight

    assert control.status("tool-control-1") == RUNNING
    cancelled = control.cancel("tool-control-1", reason="user pressed stop")

    assert cancelled.status == CANCELLED
    assert cancelled.cancelled_at is not None
    assert cancelled.error == "user pressed stop"
    assert cancelled.result is None

    worker.join(timeout=5)
    # The work finished after cancellation, and did not overwrite the verdict.
    assert control.status("tool-control-1") == CANCELLED
    assert outcome["record"].status == CANCELLED
    assert outcome["record"].result is None
    assert [o.status for o in control.orphaned()] == [SUCCEEDED]


def test_repeated_cancellation_is_idempotent():
    tool = SlowTool(delay=0.3)
    stack = build(tool=tool)
    control = stack["control"]
    threading.Thread(
        target=lambda: control.execute_with_timeout(plan_for(stack), "user:ada", timeout=5)
    ).start()
    time.sleep(0.05)

    first = control.cancel("tool-control-1")
    second = control.cancel("tool-control-1")
    third = control.cancel("tool-control-1", reason="a different reason")

    assert first.status == second.status == third.status == CANCELLED
    assert second is first
    assert third is first
    assert third.cancelled_at == first.cancelled_at
    assert third.error == first.error  # the first reason stands
    time.sleep(0.5)


def test_cancellation_after_completion_is_refused():
    stack = build()
    control = stack["control"]
    record = control.execute_with_timeout(plan_for(stack), "user:ada", timeout=5)
    assert record.status == SUCCEEDED

    with pytest.raises(ExecutionAlreadyCompletedError, match=SUCCEEDED):
        control.cancel(record.execution_id)

    # ...and the completed record is untouched by the attempt.
    assert control.status(record.execution_id) == SUCCEEDED
    assert control.get(record.execution_id).cancelled_at is None


def test_cancelling_an_unknown_execution_is_refused():
    stack = build()

    for method in (stack["control"].cancel, stack["control"].status, stack["control"].get):
        with pytest.raises(UnknownControlledExecutionError):
            method("does-not-exist")


# ---------------------------------------------------------------------------
# timeout + retry / idempotency interaction
# ---------------------------------------------------------------------------


def test_a_timed_out_call_whose_work_failed_is_retried():
    """Nothing succeeded, so Commit #9 memoized nothing and the retry runs
    the tool again."""
    tool = SlowTool(delay=0.3, fail_times=1)
    stack = build(tool=tool, with_idempotency=True)
    control, idempotency = stack["control"], stack["idempotency"]
    plan = plan_for(stack)
    key = idempotency.key(plan, "user:ada")

    timed_out = control.execute_with_timeout(plan, "user:ada", timeout=0.05)
    assert timed_out.status == TIMED_OUT

    time.sleep(0.5)  # the orphaned worker finishes -- and it failed
    assert idempotency.existing(key) is None
    assert [o.status for o in control.orphaned()] == [FAILED]

    tool.delay = 0.0
    retried = control.execute_with_timeout(plan_for(stack), "user:ada", timeout=5)

    assert retried.status == SUCCEEDED
    assert tool.calls == 2  # it genuinely ran again


def test_a_timed_out_call_whose_work_succeeded_is_not_run_twice():
    """The caller gave up waiting, but the work completed. Commit #9 memoizes
    that success, so a retry returns it instead of repeating the tool's side
    effects -- while the timed-out record stays TIMED_OUT."""
    tool = SlowTool(delay=0.3)
    stack = build(tool=tool, with_idempotency=True)
    control, idempotency = stack["control"], stack["idempotency"]
    plan = plan_for(stack)
    key = idempotency.key(plan, "user:ada")

    timed_out = control.execute_with_timeout(plan, "user:ada", timeout=0.05)
    assert timed_out.status == TIMED_OUT

    time.sleep(0.5)  # the orphaned worker finishes and memoizes its success
    assert idempotency.existing(key) is not None

    retried = control.execute_with_timeout(plan_for(stack), "user:ada", timeout=5)

    assert retried.status == SUCCEEDED
    assert tool.calls == 1  # reused, not repeated
    # The earlier call's own verdict is unchanged.
    assert control.status(timed_out.execution_id) == TIMED_OUT


def test_a_successful_controlled_call_is_memoized_once():
    stack = build(with_idempotency=True)
    control, idempotency = stack["control"], stack["idempotency"]

    first = control.execute_with_timeout(plan_for(stack), "user:ada", timeout=5)
    second = control.execute_with_timeout(plan_for(stack), "user:ada", timeout=5)

    assert first.status == second.status == SUCCEEDED
    assert stack["tool"].calls == 1
    assert idempotency.reuse_count(idempotency.key(plan_for(stack), "user:ada")) == 1


# ---------------------------------------------------------------------------
# audit / status consistency
# ---------------------------------------------------------------------------


def test_audit_records_the_controlled_outcome():
    stack = build(with_audit=True)
    control, audit = stack["control"], stack["audit"]
    plan = plan_for(stack)
    audit.start(plan, "conversation-1", subject="user:ada")

    record = control.execute_with_timeout(plan, "user:ada", timeout=5)

    assert [a.status for a in audit.trail(plan.plan_id)] == ["PLANNED", SUCCEEDED]
    assert audit.get(record.execution_id).status == control.status(record.execution_id)


def test_a_timeout_is_audited_as_a_timeout():
    stack = build(tool=SlowTool(delay=0.5), with_audit=True)
    control, audit = stack["control"], stack["audit"]
    plan = plan_for(stack)
    audit.start(plan, "conversation-1", subject="user:ada")

    record = control.execute_with_timeout(plan, "user:ada", timeout=0.05)

    assert record.status == TIMED_OUT
    assert audit.trail(plan.plan_id)[-1].status == TIMED_OUT
    assert audit.get(record.execution_id).status == TIMED_OUT
    time.sleep(0.6)
    # The late success never reaches the trail.
    assert audit.trail(plan.plan_id)[-1].status == TIMED_OUT


def test_a_cancellation_is_audited():
    stack = build(tool=SlowTool(delay=0.3), with_audit=True)
    control, audit = stack["control"], stack["audit"]
    plan = plan_for(stack)
    audit.start(plan, "conversation-1", subject="user:ada")
    threading.Thread(
        target=lambda: control.execute_with_timeout(plan, "user:ada", timeout=5)
    ).start()
    time.sleep(0.05)

    control.cancel("tool-control-1")

    assert audit.trail(plan.plan_id)[-1].status == CANCELLED
    time.sleep(0.5)
    assert audit.trail(plan.plan_id)[-1].status == CANCELLED


def test_a_controlled_outcome_normalizes_for_the_model():
    """Commit #6 accepts the new statuses because they joined the execution
    vocabulary rather than forming a separate one."""
    stack = build(tool=SlowTool(delay=0.5))
    results = LLMToolResultService()

    record = stack["control"].execute_with_timeout(plan_for(stack), "user:ada", timeout=0.05)
    normalized = results.normalize(record)

    assert normalized.status == TIMED_OUT
    assert normalized.output is None
    assert "deadline" in normalized.error
    assert results.validate(normalized) is True
    results.context(normalized).validate()
