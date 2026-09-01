import threading
import time
from datetime import datetime, timezone

import pytest

from backend.agent_checkpointing import LLMAgentCheckpointService
from backend.agent_execution_context import (
    DuplicateStepContextError,
    LLMAgentExecutionContextService,
    UnknownAgentExecutionContextError,
    UnknownStepContextError,
    UnverifiedStepResultError,
)
from backend.agent_execution_recovery import LLMAgentRecoveryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService, LLMAgentStepExecution
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.context import estimate_text_tokens
from backend.llm.tool_audit import LLMToolAuditService
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import FAILED, LLMToolExecutionService, SUCCEEDED
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


def make_bulky(size):
    def handler(topic):
        return {"topic": topic, "blob": "x" * size}

    return handler


def leaks_a_secret(topic):
    return {"topic": topic, "api_key": "sk-abcdefghijklmnopqrstuvwx"}


class FixedPlanStore:
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


def build(tools=None):
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

    return {"registry": registry, "invocation": invocation, "permissions": permissions, "orchestrator": orchestrator}


def wire(stack, plan):
    """Point Commit #2/#3/#4/#5/#6/#7 at a directly-built plan sharing one stack's tools."""
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    plan_execution = LLMAgentPlanExecutionService(store, validation_service, step_execution)
    checkpoints = LLMAgentCheckpointService(store, validation_service, step_execution, plan_execution)
    recovery = LLMAgentRecoveryService(store, validation_service, step_execution, plan_execution, checkpoints)
    context = LLMAgentExecutionContextService(store, step_execution)
    return step_execution, plan_execution, checkpoints, recovery, context


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


def test_successful_result_injection():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    step_execution, _, _, _, context = wire(stack, plan)
    execution = step_execution.execute_step("plan-1", "step-1", "user:ada")

    item = context.record_step("exec-1", "step-1", execution)

    assert item.type == "tool"
    assert '"status": "SUCCEEDED"' in item.content
    assert '"found": true' in item.content.lower()
    assert context.for_step("exec-1", "step-1") == item
    built = context.context("exec-1")
    assert len(built["messages"]) == 1
    assert built["messages"][0]["content"] == item.content


def test_multi_step_context_ordering():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, _, _, _, context = wire(stack, plan)
    first = step_execution.execute_step("plan-1", "step-1", "user:ada")
    second = step_execution.execute_step("plan-1", "step-2", "user:ada")

    context.record_step("exec-1", "step-1", first)
    context.record_step("exec-1", "step-2", second)

    assert context.steps("exec-1") == ["step-1", "step-2"]
    built = context.context("exec-1")
    assert [msg["content"] for msg in built["messages"]] == [
        context.for_step("exec-1", "step-1").content,
        context.for_step("exec-1", "step-2").content,
    ]


def test_failed_result_is_marked_explicitly_not_dropped():
    stack = build(tools={"broken": always_fails})
    plan = _plan("plan-1", [_step("step-1", "broken")])
    step_execution, _, _, _, context = wire(stack, plan)
    execution = step_execution.execute_step("plan-1", "step-1", "user:ada")
    assert execution.status == FAILED

    item = context.record_step("exec-1", "step-1", execution)

    assert '"status": "FAILED"' in item.content
    assert "upstream lookup service is down" in item.content
    assert '"output"' not in item.content
    built = context.context("exec-1")
    assert len(built["messages"]) == 1


def test_token_budget_enforcement_drops_what_does_not_fit():
    stack = build(tools={"bulky": make_bulky(4000), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "bulky"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, _, _, _, context = wire(stack, plan)
    first = step_execution.execute_step("plan-1", "step-1", "user:ada")
    second = step_execution.execute_step("plan-1", "step-2", "user:ada")

    # Learn each item's real rendered cost first, then cap the budget to fit
    # only the first.
    probe = LLMAgentExecutionContextService(FixedPlanStore(plan), step_execution)
    probe.record_step("probe", "step-1", first)
    probe.record_step("probe", "step-2", second)
    cost1 = estimate_text_tokens(probe.for_step("probe", "step-1").content)
    cost2 = estimate_text_tokens(probe.for_step("probe", "step-2").content)
    assert cost1 + cost2 > cost1 + 5  # sanity: both items together would not fit a cost1-sized budget

    tight = LLMAgentExecutionContextService(FixedPlanStore(plan), step_execution)
    tight.record_step("exec-1", "step-1", first, token_budget=cost1 + 5)
    tight.record_step("exec-1", "step-2", second)

    built = tight.context("exec-1")
    assert len(built["messages"]) == 1
    assert built["messages"][0]["content"] == tight.for_step("exec-1", "step-1").content


def test_security_redaction_integration():
    stack = build(tools={"leaky": leaks_a_secret})
    plan = _plan("plan-1", [_step("step-1", "leaky")])
    step_execution, _, _, _, context = wire(stack, plan)
    execution = step_execution.execute_step("plan-1", "step-1", "user:ada")

    item = context.record_step("exec-1", "step-1", execution)

    assert "sk-abcdefghijklmnopqrstuvwx" not in item.content
    assert "[REDACTED]" in item.content


def test_recovery_context_preservation():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, plan_execution, checkpoints, recovery, context = wire(stack, plan)
    outcome = {}

    def run():
        outcome["execution"] = plan_execution.execute("plan-1", "user:ada")

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.02)
    plan_execution.cancel("agent-plan-execution-1")
    worker.join(timeout=5)
    execution_id = outcome["execution"].execution_id
    checkpoints.save(execution_id)

    step1_record = step_execution.executions("plan-1")[0]
    context.record_step(execution_id, "step-1", step1_record)

    recovery.recover(execution_id, subject="user:ada")

    # Replaying step-1 (unchanged) after recovery must be a safe no-op, and
    # step-2's freshly-completed result must now also be recordable.
    same_item = context.record_step(execution_id, "step-1", step1_record)
    assert same_item == context.for_step(execution_id, "step-1")

    step2_record = next(r for r in step_execution.executions("plan-1") if r.step_id == "step-2")
    context.record_step(execution_id, "step-2", step2_record)

    assert context.steps(execution_id) == ["step-1", "step-2"]
    assert len(context.context(execution_id)["messages"]) == 2


def test_step_isolation_between_executions():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    step_execution, _, _, _, context = wire(stack, plan)
    a = step_execution.execute_step("plan-1", "step-1", "user:ada")

    context.record_step("exec-a", "step-1", a)

    with pytest.raises(UnknownAgentExecutionContextError):
        context.context("exec-b")
    with pytest.raises(UnknownAgentExecutionContextError):
        context.for_step("exec-b", "step-1")
    assert context.steps("exec-a") == ["step-1"]


def test_unverified_result_is_rejected():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    step_execution, _, _, _, context = wire(stack, plan)
    real = step_execution.execute_step("plan-1", "step-1", "user:ada")
    forged = LLMAgentStepExecution(
        execution_id=real.execution_id, plan_id=real.plan_id, step_id=real.step_id,
        status=SUCCEEDED, result=None, error=None,
        started_at=real.started_at, completed_at=real.completed_at,
    )

    with pytest.raises(UnverifiedStepResultError):
        context.record_step("exec-1", "step-1", forged)


def test_duplicate_step_with_a_different_result_is_rejected():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    step_execution, _, _, _, context = wire(stack, plan)
    first = step_execution.execute_step("plan-1", "step-1", "user:ada")
    context.record_step("exec-1", "step-1", first)

    # A second, genuinely different Commit #3 execution for the same step.
    second = step_execution.execute_step("plan-1", "step-1", "user:ada")
    assert second.execution_id != first.execution_id

    with pytest.raises(DuplicateStepContextError):
        context.record_step("exec-1", "step-1", second)


def test_unknown_step_context_raises():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    step_execution, _, _, _, context = wire(stack, plan)
    execution = step_execution.execute_step("plan-1", "step-1", "user:ada")
    context.record_step("exec-1", "step-1", execution)

    with pytest.raises(UnknownStepContextError):
        context.for_step("exec-1", "no-such-step")
