import threading
import time
from datetime import datetime, timezone

import pytest

from backend.agent_checkpointing import LLMAgentCheckpointService
from backend.agent_execution_budget import (
    BUDGET_EXCEEDED,
    WITHIN_BUDGET,
    LLMAgentExecutionBudgetService,
    UnknownExecutionBudgetError,
)
from backend.agent_execution_recovery import LLMAgentRecoveryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.budget import BudgetExceededError
from backend.llm.tool_audit import LLMToolAuditService
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import LLMToolExecutionService
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


def make_slow(delay):
    def handler(topic):
        time.sleep(delay)
        return {"topic": topic, "found": True}

    return handler


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
    """Point Commit #2/#3/#4/#5/#6 at a directly-built plan sharing one stack's tools."""
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    plan_execution = LLMAgentPlanExecutionService(store, validation_service, step_execution)
    checkpoints = LLMAgentCheckpointService(store, validation_service, step_execution, plan_execution)
    recovery = LLMAgentRecoveryService(store, validation_service, step_execution, plan_execution, checkpoints)
    return step_execution, plan_execution, checkpoints, recovery


def interrupt_after_first_step(plan_execution, plan_id="plan-1"):
    outcome = {}

    def run():
        outcome["execution"] = plan_execution.execute(plan_id, "user:ada")

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.02)
    plan_execution.cancel("agent-plan-execution-1")
    worker.join(timeout=5)
    return outcome["execution"]


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


def test_within_budget():
    budgets = LLMAgentExecutionBudgetService()
    budgets.configure("exec-1", max_steps=5, max_tokens=1000, max_cost=1.0, max_duration=60.0)

    budgets.consume("exec-1", {"steps": 1, "tokens": 100, "cost": 0.1, "duration": 2.0})

    assert budgets.check("exec-1") is True
    assert budgets.exceeded("exec-1") == WITHIN_BUDGET
    remaining = budgets.remaining("exec-1")
    assert remaining == {"steps": 4, "tokens": 900, "cost": pytest.approx(0.9), "duration": pytest.approx(58.0)}


def test_step_limit():
    budgets = LLMAgentExecutionBudgetService()
    budgets.configure("exec-1", max_steps=2)

    budgets.consume("exec-1", {"steps": 1})
    assert budgets.exceeded("exec-1") == WITHIN_BUDGET
    assert budgets.check("exec-1") is True

    budgets.consume("exec-1", {"steps": 1})
    assert budgets.exceeded("exec-1") == BUDGET_EXCEEDED
    with pytest.raises(BudgetExceededError, match="steps"):
        budgets.check("exec-1")


def test_token_limit():
    budgets = LLMAgentExecutionBudgetService()
    budgets.configure("exec-1", max_tokens=100)

    budgets.consume("exec-1", {"tokens": 60})
    assert budgets.check("exec-1") is True

    budgets.consume("exec-1", {"tokens": 50})
    assert budgets.exceeded("exec-1") == BUDGET_EXCEEDED
    with pytest.raises(BudgetExceededError, match="tokens"):
        budgets.check("exec-1")


def test_cost_limit():
    budgets = LLMAgentExecutionBudgetService()
    budgets.configure("exec-1", max_cost=1.0)

    budgets.consume("exec-1", {"cost": 0.6})
    assert budgets.check("exec-1") is True

    budgets.consume("exec-1", {"cost": 0.5})
    assert budgets.exceeded("exec-1") == BUDGET_EXCEEDED
    with pytest.raises(BudgetExceededError, match="cost"):
        budgets.check("exec-1")


def test_duration_limit():
    budgets = LLMAgentExecutionBudgetService()
    budgets.configure("exec-1", max_duration=10.0)

    budgets.consume("exec-1", {"duration": 6.0})
    assert budgets.check("exec-1") is True

    budgets.consume("exec-1", {"duration": 5.0})
    assert budgets.exceeded("exec-1") == BUDGET_EXCEEDED
    with pytest.raises(BudgetExceededError, match="duration"):
        budgets.check("exec-1")


def test_budget_exhaustion_reports_every_violated_dimension():
    budgets = LLMAgentExecutionBudgetService()
    budgets.configure("exec-1", max_steps=1, max_tokens=10, max_cost=0.1, max_duration=1.0)

    budgets.consume("exec-1", {"steps": 2, "tokens": 20, "cost": 0.5, "duration": 5.0})

    assert budgets.exceeded("exec-1") == BUDGET_EXCEEDED
    with pytest.raises(BudgetExceededError) as excinfo:
        budgets.check("exec-1")
    for dimension in ("steps", "tokens", "cost", "duration"):
        assert dimension in str(excinfo.value)


def test_recovery_preserves_consumed_usage():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, plan_execution, checkpoints, recovery = wire(stack, plan)
    budgets = LLMAgentExecutionBudgetService()

    execution = interrupt_after_first_step(plan_execution)
    checkpoints.save(execution.execution_id)
    budgets.configure(execution.execution_id, max_steps=10)

    step1 = step_execution.executions("plan-1")[0]
    budgets.consume_step(execution.execution_id, step1)
    usage_before = budgets.remaining(execution.execution_id)["steps"]

    recovery.recover(execution.execution_id, subject="user:ada")

    # Re-configuring (as a caller resuming after an interruption might) must
    # not erase what was already consumed.
    budgets.configure(execution.execution_id, max_steps=10)
    assert budgets.remaining(execution.execution_id)["steps"] == usage_before

    step2 = next(r for r in step_execution.executions("plan-1") if r.step_id == "step-2")
    budgets.consume_step(execution.execution_id, step2)

    assert budgets.remaining(execution.execution_id)["steps"] == usage_before - 1


def test_concurrent_consumption_is_not_lost():
    budgets = LLMAgentExecutionBudgetService()
    budgets.configure("exec-1", max_steps=1000)

    def consume_once():
        budgets.consume("exec-1", {"steps": 1})

    threads = [threading.Thread(target=consume_once) for _ in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert budgets.remaining("exec-1")["steps"] == 1000 - 50


def test_unknown_execution_raises():
    budgets = LLMAgentExecutionBudgetService()

    with pytest.raises(UnknownExecutionBudgetError):
        budgets.check("no-such-execution")
    with pytest.raises(UnknownExecutionBudgetError):
        budgets.consume("no-such-execution", {"steps": 1})
    with pytest.raises(UnknownExecutionBudgetError):
        budgets.remaining("no-such-execution")
    with pytest.raises(UnknownExecutionBudgetError):
        budgets.exceeded("no-such-execution")
