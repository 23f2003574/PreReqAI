import threading
import time

import pytest

from backend.llm.retry import (
    InvalidRetryPolicyError,
    LLMRetryPolicy,
    LLMRetryService,
    PermanentLLMError,
    TransientLLMError,
)
from backend.llm.tool_audit import LLMToolAuditService
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import (
    CANCELLED,
    DENIED,
    FAILED,
    LLMToolExecutionService,
    REJECTED,
    SUCCEEDED,
    TIMED_OUT,
)
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_permissions import (
    ANY_SUBJECT,
    LLMToolPermissionPolicy,
    LLMToolPermissionService,
)
from backend.llm.tool_retry import (
    DEFAULT_POLICY,
    LLMToolRetryPolicy,
    LLMToolRetryService,
)
from backend.llm.tools import LLMToolRegistryService

SUMMARIZE_SCHEMA = {
    "type": "object",
    "properties": {"analysis_id": {"type": "string"}},
    "required": ["analysis_id"],
}


class FlakyTool:
    """A real handler that fails a set number of times, then succeeds."""

    def __init__(self, failures=0, error=None, delay=0.0):
        self.failures = failures
        self.error = error or TransientLLMError("upstream is briefly unavailable")
        self.delay = delay
        self.calls = 0

    def __call__(self, analysis_id):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.calls <= self.failures:
            raise self.error
        return {"analysis_id": analysis_id, "cell_count": 3}


class RecordingSleeper:
    def __init__(self):
        self.slept = []

    def __call__(self, seconds):
        self.slept.append(seconds)


def build(tool=None, policy=None, allow=True, with_audit=False):
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
    execution = LLMToolExecutionService(registry, permissions)
    execution.bind("summarize_notebook_analysis", tool)
    control = LLMToolExecutionControlService(execution)
    audit = LLMToolAuditService() if with_audit else None
    sleeper = RecordingSleeper()
    retry = LLMToolRetryService(
        control, execution, policy or DEFAULT_POLICY, audit, sleeper
    )
    return {
        "registry": registry,
        "invocation": invocation,
        "permissions": permissions,
        "execution": execution,
        "control": control,
        "audit": audit,
        "retry": retry,
        "tool": tool,
        "sleeper": sleeper,
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
# policy
# ---------------------------------------------------------------------------


def test_policy_reuses_the_existing_retry_policy():
    policy = LLMToolRetryPolicy(policy_id="p", max_attempts=4, backoff=0.5)

    converted = policy.as_retry_policy()

    assert isinstance(converted, LLMRetryPolicy)
    assert converted.max_attempts == 4
    assert converted.backoff_seconds == 0.5
    assert converted.policy_id == "p"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"max_attempts": -1},
        {"max_attempts": "3"},
        {"backoff": -1},
        {"policy_id": ""},
        {"retryable_errors": [TransientLLMError]},
        {"retryable_errors": (123,)},
    ],
)
def test_a_malformed_policy_is_refused_by_the_existing_validation(kwargs):
    fields = {"policy_id": "p", "max_attempts": 3, "backoff": 0.0}
    fields.update(kwargs)

    with pytest.raises(InvalidRetryPolicyError):
        LLMToolRetryPolicy(**fields)


@pytest.mark.parametrize("status", [DENIED, REJECTED, CANCELLED])
def test_a_gate_refusal_cannot_be_declared_retryable(status):
    with pytest.raises(InvalidRetryPolicyError, match="never be retryable"):
        LLMToolRetryPolicy(retryable_errors=(status,))


# ---------------------------------------------------------------------------
# should_retry
# ---------------------------------------------------------------------------


def test_should_retry_only_explicit_errors():
    stack = build(policy=LLMToolRetryPolicy(retryable_errors=(TransientLLMError,)))
    retry = stack["retry"]

    assert retry.should_retry(TransientLLMError("blip")) is True
    assert retry.should_retry(PermanentLLMError("bad request")) is False
    assert retry.should_retry(RuntimeError("something else")) is False
    # Commit #5 stores a failure as "ClassName: detail".
    assert retry.should_retry("TransientLLMError: blip") is True
    assert retry.should_retry("PermanentLLMError: nope") is False
    assert retry.should_retry(None) is False


def test_a_disabled_policy_retries_nothing():
    stack = build(policy=LLMToolRetryPolicy(enabled=False, max_attempts=5))

    assert stack["retry"].should_retry(TransientLLMError("blip")) is False
    assert stack["retry"].policy.attempt_limit == 1


def test_a_status_may_be_declared_retryable():
    stack = build(policy=LLMToolRetryPolicy(retryable_errors=(TIMED_OUT,)))

    assert stack["retry"].should_retry(TIMED_OUT) is True
    assert stack["retry"].should_retry(TransientLLMError("blip")) is False


# ---------------------------------------------------------------------------
# retrying
# ---------------------------------------------------------------------------


def test_transient_failure_is_retried_until_it_succeeds():
    stack = build(tool=FlakyTool(failures=2))

    record = stack["retry"].execute(plan_for(stack), "user:ada")

    assert record.status == SUCCEEDED
    assert record.result == {"analysis_id": "analysis-1", "cell_count": 3}
    assert stack["tool"].calls == 3
    assert stack["retry"].attempts(record.execution_id) == 3


def test_a_permanent_failure_is_not_retried():
    stack = build(tool=FlakyTool(failures=5, error=PermanentLLMError("bad request")))

    record = stack["retry"].execute(plan_for(stack), "user:ada")

    assert record.status == FAILED
    assert "PermanentLLMError" in record.error
    assert stack["tool"].calls == 1
    assert stack["retry"].attempts(record.execution_id) == 1


def test_an_unlisted_exception_is_not_retried():
    stack = build(tool=FlakyTool(failures=5, error=RuntimeError("unexpected")))

    record = stack["retry"].execute(plan_for(stack), "user:ada")

    assert record.status == FAILED
    assert stack["tool"].calls == 1


def test_max_attempts_is_enforced():
    stack = build(
        tool=FlakyTool(failures=99),
        policy=LLMToolRetryPolicy(max_attempts=3, retryable_errors=(TransientLLMError,)),
    )

    record = stack["retry"].execute(plan_for(stack), "user:ada")

    assert record.status == FAILED
    assert stack["tool"].calls == 3
    assert stack["retry"].attempts(record.execution_id) == 3
    # Exhaustion is a record, not an exception, at this layer.
    assert isinstance(record.error, str)


def test_a_disabled_policy_allows_exactly_one_attempt():
    stack = build(
        tool=FlakyTool(failures=99),
        policy=LLMToolRetryPolicy(max_attempts=5, enabled=False),
    )

    record = stack["retry"].execute(plan_for(stack), "user:ada")

    assert record.status == FAILED
    assert stack["tool"].calls == 1


# ---------------------------------------------------------------------------
# never retrying a gate's refusal
# ---------------------------------------------------------------------------


def test_an_authorization_failure_is_never_retried():
    stack = build(tool=FlakyTool(failures=99), allow=False)

    record = stack["retry"].execute(plan_for(stack), "user:ada")

    assert record.status == DENIED
    assert stack["tool"].calls == 0
    assert stack["retry"].attempts(record.execution_id) == 1


def test_a_validation_failure_is_never_retried():
    stack = build()
    bad = stack["invocation"].plan(
        {"name": "summarize_notebook_analysis", "arguments": {"shell": "rm -rf /"}}
    )

    record = stack["retry"].execute(bad, "user:ada")

    assert record.status == DENIED  # Commit #4 refuses a non-READY plan
    assert stack["tool"].calls == 0
    assert stack["retry"].attempts(record.execution_id) == 1


def test_a_disabled_tool_is_never_retried():
    stack = build()
    plan = plan_for(stack)
    stack["registry"].disable("summarize_notebook_analysis")

    record = stack["retry"].execute(plan, "user:ada")

    assert record.status == REJECTED
    assert stack["tool"].calls == 0
    assert stack["retry"].attempts(record.execution_id) == 1


# ---------------------------------------------------------------------------
# backoff
# ---------------------------------------------------------------------------


def test_backoff_uses_the_existing_schedule():
    policy = LLMToolRetryPolicy(max_attempts=5, backoff=0.5)
    converted = policy.as_retry_policy()

    # The one exponential definition in the codebase.
    assert LLMRetryService.compute_backoff(converted, 1) == pytest.approx(0.5)
    assert LLMRetryService.compute_backoff(converted, 2) == pytest.approx(1.0)
    assert LLMRetryService.compute_backoff(converted, 3) == pytest.approx(2.0)


def test_backoff_is_applied_between_attempts():
    stack = build(
        tool=FlakyTool(failures=3),
        policy=LLMToolRetryPolicy(
            max_attempts=4, backoff=0.5, retryable_errors=(TransientLLMError,)
        ),
    )

    record = stack["retry"].execute(plan_for(stack), "user:ada")

    assert record.status == SUCCEEDED
    assert stack["sleeper"].slept == [0.5, 1.0, 2.0]
    assert stack["retry"].delays(record.execution_id) == [0.5, 1.0, 2.0]


def test_no_backoff_is_waited_after_the_final_attempt():
    stack = build(
        tool=FlakyTool(failures=99),
        policy=LLMToolRetryPolicy(max_attempts=2, backoff=0.25),
    )

    stack["retry"].execute(plan_for(stack), "user:ada")

    assert stack["sleeper"].slept == [0.25]  # one gap between two attempts


def test_a_zero_backoff_waits_not_at_all():
    stack = build(tool=FlakyTool(failures=2))

    stack["retry"].execute(plan_for(stack), "user:ada")

    assert stack["sleeper"].slept == []


# ---------------------------------------------------------------------------
# timeout and cancellation
# ---------------------------------------------------------------------------


def test_a_timeout_is_respected_per_attempt():
    stack = build(
        tool=FlakyTool(failures=0, delay=0.4),
        policy=LLMToolRetryPolicy(max_attempts=2, backoff=0.0, retryable_errors=(TIMED_OUT,)),
    )

    record = stack["retry"].execute(plan_for(stack), "user:ada", timeout=0.05)

    assert record.status == TIMED_OUT
    assert stack["retry"].attempts(record.execution_id) == 2
    time.sleep(0.9)  # let the orphaned workers finish


def test_a_timeout_is_not_retried_unless_declared():
    stack = build(
        tool=FlakyTool(failures=0, delay=0.3),
        policy=LLMToolRetryPolicy(max_attempts=3, retryable_errors=(TransientLLMError,)),
    )

    record = stack["retry"].execute(plan_for(stack), "user:ada", timeout=0.05)

    assert record.status == TIMED_OUT
    assert stack["retry"].attempts(record.execution_id) == 1
    time.sleep(0.5)


def test_cancellation_during_retry_stops_immediately():
    """A caller that cancelled did not ask for another attempt."""
    stack = build(
        tool=FlakyTool(failures=99, delay=0.25),
        policy=LLMToolRetryPolicy(
            max_attempts=5, backoff=0.0, retryable_errors=(TransientLLMError, TIMED_OUT)
        ),
    )
    control, retry = stack["control"], stack["retry"]
    outcome = {}

    def run():
        outcome["record"] = retry.execute(plan_for(stack), "user:ada", timeout=5)

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.05)

    control.cancel("tool-control-1", reason="user pressed stop")
    worker.join(timeout=5)

    assert outcome["record"].status == CANCELLED
    assert retry.attempts(outcome["record"].execution_id) == 1
    assert stack["tool"].calls == 1  # no further attempt was started


def test_a_timeout_needs_a_control_service():
    registry = LLMToolRegistryService()
    registry.register("summarize_notebook_analysis", "Summarize.", SUMMARIZE_SCHEMA)
    permissions = LLMToolPermissionService(registry)
    execution = LLMToolExecutionService(registry, permissions)
    retry = LLMToolRetryService(execution_service=execution)
    invocation = LLMToolInvocationService(registry)
    plan = invocation.plan(
        {"name": "summarize_notebook_analysis", "arguments": {"analysis_id": "a-1"}}
    )

    with pytest.raises(ValueError, match="control_service"):
        retry.execute(plan, "user:ada", timeout=1)


def test_a_service_needs_something_to_execute_with():
    with pytest.raises(ValueError, match="required"):
        LLMToolRetryService()


def test_execute_rejects_a_non_plan():
    stack = build()

    with pytest.raises(TypeError):
        stack["retry"].execute({"name": "summarize_notebook_analysis"}, "user:ada")


# ---------------------------------------------------------------------------
# one logical trail
# ---------------------------------------------------------------------------


def test_attempts_are_reachable_by_any_attempts_execution_id():
    """Every attempt belongs to one logical call."""
    stack = build(tool=FlakyTool(failures=2))
    retry = stack["retry"]

    record = retry.execute(plan_for(stack), "user:ada")

    ids = [e.execution_id for e in stack["execution"].executions()]
    assert len(ids) == 3
    for execution_id in ids:
        assert retry.attempts(execution_id) == 3
    assert retry.attempts(record.execution_id) == 3


def test_audit_consistency_records_every_attempt():
    """The trail shows the retries rather than hiding them, and its final
    status agrees with the record the caller was handed."""
    stack = build(tool=FlakyTool(failures=2), with_audit=True)
    retry, audit = stack["retry"], stack["audit"]
    plan = plan_for(stack)
    audit.start(plan, "conversation-1", subject="user:ada")

    record = retry.execute(plan, "user:ada")

    trail = audit.trail(plan.plan_id)
    assert [a.status for a in trail] == ["PLANNED", FAILED, FAILED, SUCCEEDED]
    assert trail[-1].status == record.status
    assert audit.get(record.execution_id).status == SUCCEEDED
    # Each attempt is its own immutable snapshot, in order.
    assert len({a.audit_id for a in trail}) == 4


def test_audit_consistency_for_an_exhausted_call():
    stack = build(
        tool=FlakyTool(failures=99),
        policy=LLMToolRetryPolicy(max_attempts=2, retryable_errors=(TransientLLMError,)),
        with_audit=True,
    )
    retry, audit = stack["retry"], stack["audit"]
    plan = plan_for(stack)
    audit.start(plan, "conversation-1", subject="user:ada")

    record = retry.execute(plan, "user:ada")

    assert record.status == FAILED
    assert [a.status for a in audit.trail(plan.plan_id)] == ["PLANNED", FAILED, FAILED]
    assert audit.get(record.execution_id).status == FAILED
