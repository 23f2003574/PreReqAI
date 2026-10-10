import threading
import time
from datetime import datetime, timezone

import pytest

from backend.agent_plan_execution import (
    LLMAgentPlanExecutionService,
    PlanExecutionAlreadyExistsError,
    UnknownAgentPlanExecutionError,
)
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.tool_audit import LLMToolAuditService
from backend.llm.tool_control import ExecutionAlreadyCompletedError, LLMToolExecutionControlService
from backend.llm.tool_execution import CANCELLED, FAILED, LLMToolExecutionService, REJECTED, SUCCEEDED
from backend.llm.tool_idempotency import LLMToolIdempotencyService
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_metrics import LLMToolMetricsService
from backend.llm.tool_orchestration import LLMToolCallingOrchestrationService
from backend.llm.tool_permissions import ANY_SUBJECT, LLMToolPermissionPolicy, LLMToolPermissionService
from backend.llm.tool_results import LLMToolResultService
from backend.llm.tool_retry import LLMToolRetryPolicy, LLMToolRetryService
from backend.llm.tools import LLMToolRegistryService

SCHEMA = {
    "type": "object",
    "properties": {"topic": {"type": "string"}},
    "required": ["topic"],
}


def ok(topic):
    return {"topic": topic, "found": True}


def always_fails(topic):
    raise RuntimeError("upstream lookup service is down")


def make_slow(delay):
    def handler(topic):
        time.sleep(delay)
        return {"topic": topic, "found": True}

    return handler


class FixedPlanStore:
    """A minimal stand-in for LLMAgentPlanningService exposing only get()."""

    def __init__(self, plan: LLMAgentPlan):
        self._plan = plan

    def get(self, plan_id: str) -> LLMAgentPlan:
        if plan_id != self._plan.plan_id:
            raise KeyError(plan_id)
        return self._plan


def _step(step_id, tool_name, depends_on=()):
    return LLMAgentPlanStep(
        step_id=step_id,
        action=f"call {tool_name}",
        tool_name=tool_name,
        arguments={"topic": "linear algebra"},
        depends_on=list(depends_on),
        status=READY,
        errors=[],
    )


def _plan(plan_id, steps):
    return LLMAgentPlan(
        plan_id=plan_id, task="a test task", steps=steps, status=READY,
        created_at=datetime.now(timezone.utc),
    )


def build(tools=None, deny_subject_on=None):
    """Wires the full existing tool-calling pipeline exactly as Commit #3's
    own tests do, then stacks Commit #1(-stand-in)/#2/#3/#4 on top of it.
    `tools` is {name: handler}, each registered against the shared SCHEMA.
    """
    tools = tools or {"lookup": ok}

    registry = LLMToolRegistryService()
    for name in tools:
        registry.register(name, f"Tool {name}", SCHEMA)

    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    for index, name in enumerate(tools):
        permissions.register(
            LLMToolPermissionPolicy(
                policy_id=f"allow-{name}-{index}", tool_name=name, subject=ANY_SUBJECT, allowed=True
            )
        )
    if deny_subject_on is not None:
        tool_name, subject = deny_subject_on
        permissions.register(
            LLMToolPermissionPolicy(
                policy_id=f"deny-{tool_name}-{subject}", tool_name=tool_name, subject=subject, allowed=False
            )
        )

    execution = LLMToolExecutionService(registry, permissions)
    for name, handler in tools.items():
        execution.bind(name, handler)

    idempotency = LLMToolIdempotencyService(execution, permissions)
    control = LLMToolExecutionControlService(execution, idempotency)
    retry = LLMToolRetryService(
        control, execution, LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
        sleeper=lambda seconds: None, idempotency_service=idempotency,
    )
    audit = LLMToolAuditService()
    metrics = LLMToolMetricsService(retry)
    results = LLMToolResultService()

    orchestrator = LLMToolCallingOrchestrationService(
        invocation_service=invocation,
        permission_service=permissions,
        execution_service=execution,
        result_service=results,
        idempotency_service=idempotency,
        control_service=control,
        retry_service=retry,
        audit_service=audit,
        metrics_service=metrics,
    )

    return {
        "registry": registry,
        "invocation": invocation,
        "permissions": permissions,
        "control": control,
        "orchestrator": orchestrator,
    }


def wire(stack, plan, permission_service=None):
    """Point Commit #2/#3/#4 at a directly-built plan sharing one stack's tools."""
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], permission_service or stack["permissions"],
        invocation_service=stack["invocation"],
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    plan_execution = LLMAgentPlanExecutionService(store, validation_service, step_execution)
    return validation_service, step_execution, plan_execution


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


def test_successful_multi_step_plan():
    stack = build()
    plan = _plan(
        "plan-1",
        [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"])],
    )
    _, step_execution, plan_execution = wire(stack, plan)

    execution = plan_execution.execute("plan-1", "user:ada")

    assert execution.status == SUCCEEDED
    assert execution.completed_steps == ["step-1", "step-2"]
    assert execution.failed_step is None
    assert execution.completed_at is not None
    assert len(step_execution.executions("plan-1")) == 2


def test_dependency_ordering_runs_prerequisites_first():
    stack = build()
    # Declared with the dependency listed *second* -- step-2 must still run
    # before step-1, since step-1 depends on it.
    plan = _plan(
        "plan-1",
        [_step("step-1", "lookup", depends_on=["step-2"]), _step("step-2", "lookup")],
    )
    _, step_execution, plan_execution = wire(stack, plan)

    execution = plan_execution.execute("plan-1", "user:ada")

    assert execution.status == SUCCEEDED
    assert execution.completed_steps == ["step-2", "step-1"]
    recorded_order = [record.step_id for record in step_execution.executions("plan-1")]
    assert recorded_order == ["step-2", "step-1"]


def test_step_failure_stops_the_plan_and_reports_partial_completion():
    stack = build(tools={"lookup": ok, "broken": always_fails})
    plan = _plan(
        "plan-1",
        [
            _step("step-1", "lookup"),
            _step("step-2", "broken", depends_on=["step-1"]),
            _step("step-3", "lookup", depends_on=["step-2"]),
        ],
    )
    _, step_execution, plan_execution = wire(stack, plan)

    execution = plan_execution.execute("plan-1", "user:ada")

    assert execution.status == FAILED
    assert execution.completed_steps == ["step-1"]
    assert execution.failed_step == "step-2"
    # step-3 depended on the failed step and must never have been attempted.
    recorded = {record.step_id for record in step_execution.executions("plan-1")}
    assert recorded == {"step-1", "step-2"}


def test_permission_failure_stops_the_plan():
    stack = build(deny_subject_on=("lookup", "user:restricted"))
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, step_execution, plan_execution = wire(stack, plan)

    execution = plan_execution.execute("plan-1", "user:restricted")

    assert execution.status == FAILED
    assert execution.failed_step == "step-1"
    assert execution.completed_steps == []
    assert step_execution.status(step_execution.executions("plan-1")[0].execution_id) == "DENIED"


def test_timeout_stops_the_plan():
    stack = build(tools={"slow": make_slow(0.4)})
    plan = _plan("plan-1", [_step("step-1", "slow")])
    _, step_execution, plan_execution = wire(stack, plan)

    execution = plan_execution.execute("plan-1", "user:ada", timeout=0.05)

    assert execution.status == FAILED
    assert execution.failed_step == "step-1"
    time.sleep(0.6)  # let the orphaned worker finish before the pool shuts down


def test_cancellation_stops_before_the_next_step():
    stack = build(tools={"slow": make_slow(0.2), "lookup": ok})
    plan = _plan(
        "plan-1",
        [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])],
    )
    _, step_execution, plan_execution = wire(stack, plan)
    outcome = {}

    def run():
        outcome["execution"] = plan_execution.execute("plan-1", "user:ada")

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.05)
    # Deterministic: this is the first (and only) plan execution created.
    plan_execution.cancel("agent-plan-execution-1")
    worker.join(timeout=5)

    execution = outcome["execution"]
    assert execution.status == CANCELLED
    assert execution.completed_steps == ["step-1"]
    assert execution.failed_step is None


def test_cancel_unknown_execution_raises():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, _, plan_execution = wire(stack, plan)

    with pytest.raises(UnknownAgentPlanExecutionError):
        plan_execution.cancel("no-such-execution")


def test_cancel_completed_execution_raises():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, _, plan_execution = wire(stack, plan)
    execution = plan_execution.execute("plan-1", "user:ada")

    with pytest.raises(ExecutionAlreadyCompletedError):
        plan_execution.cancel(execution.execution_id)


def test_final_execution_status_is_queryable():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, _, plan_execution = wire(stack, plan)

    execution = plan_execution.execute("plan-1", "user:ada")

    assert plan_execution.status(execution.execution_id) == SUCCEEDED
    assert plan_execution.get(execution.execution_id) == execution


def test_duplicate_execution_is_rejected():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, _, plan_execution = wire(stack, plan)
    plan_execution.execute("plan-1", "user:ada")

    with pytest.raises(PlanExecutionAlreadyExistsError):
        plan_execution.execute("plan-1", "user:ada")


def test_invalid_plan_never_starts_a_single_step():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "no_such_tool")])
    _, step_execution, plan_execution = wire(stack, plan)

    execution = plan_execution.execute("plan-1", "user:ada")

    assert execution.status == REJECTED
    assert execution.completed_steps == []
    assert execution.failed_step is None
    assert step_execution.executions("plan-1") == []


def test_steps_delegates_to_commit3_records_without_duplicating_them():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, step_execution, plan_execution = wire(stack, plan)

    execution = plan_execution.execute("plan-1", "user:ada")

    assert plan_execution.steps(execution.execution_id) == step_execution.executions("plan-1")


def test_unknown_plan_raises():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, _, plan_execution = wire(stack, plan)

    with pytest.raises(KeyError):
        plan_execution.execute("no-such-plan", "user:ada")
