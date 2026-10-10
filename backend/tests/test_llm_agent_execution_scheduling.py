import threading
import time
from datetime import datetime, timezone

import pytest

from backend.agent_dependency_resolution import LLMAgentDependencyService
from backend.agent_execution_budget import LLMAgentExecutionBudgetService
from backend.agent_execution_scheduling import LLMAgentSchedulerService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
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


def wire(stack, plan, budget_service=None, with_plan_execution=True):
    """Point Commit #2/#3/#4/#8/#11 at a directly-built plan sharing one stack's tools."""
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    plan_execution = LLMAgentPlanExecutionService(store, validation_service, step_execution) if with_plan_execution else None
    dependencies = LLMAgentDependencyService(store, step_execution, plan_execution)
    scheduler = LLMAgentSchedulerService(dependencies, budget_service, plan_execution)
    return step_execution, plan_execution, dependencies, scheduler


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


def test_ready_step_scheduling():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, _, _, scheduler = wire(stack, plan, with_plan_execution=False)

    assert scheduler.schedule("plan-1") == ["step-1"]
    assert scheduler.next_step("plan-1") == "step-1"


def test_dependency_blocking():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, _, _, scheduler = wire(stack, plan, with_plan_execution=False)

    assert scheduler.schedule("plan-1") == ["step-1"]

    step_execution.execute_step("plan-1", "step-1", "user:ada")

    assert scheduler.schedule("plan-1") == ["step-2"]


def test_budget_exhaustion_blocks_scheduling():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    budgets = LLMAgentExecutionBudgetService()
    budgets.configure("plan-1", max_steps=1)
    _, _, _, scheduler = wire(stack, plan, budget_service=budgets, with_plan_execution=False)

    assert scheduler.schedule("plan-1") == ["step-1"]

    budgets.consume("plan-1", {"steps": 1})

    assert scheduler.schedule("plan-1") == []
    assert scheduler.next_step("plan-1") is None
    # The raw dependency view is unaffected by budget -- only schedule() gates it.
    assert scheduler.ready("plan-1") == ["step-1"]


def test_completed_step_exclusion():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    step_execution, _, _, scheduler = wire(stack, plan, with_plan_execution=False)

    step_execution.execute_step("plan-1", "step-1", "user:ada")

    assert scheduler.schedule("plan-1") == []
    assert scheduler.next_step("plan-1") is None


def test_deterministic_ordering_follows_plan_declaration():
    stack = build()
    plan = _plan("plan-1", [_step("step-b", "lookup"), _step("step-a", "lookup")])
    _, _, _, scheduler = wire(stack, plan, with_plan_execution=False)

    assert scheduler.schedule("plan-1") == ["step-b", "step-a"]
    assert scheduler.next_step("plan-1") == "step-b"


def test_parallel_ready_steps():
    stack = build()
    plan = _plan(
        "plan-1",
        [_step("step-1", "lookup"), _step("step-2", "lookup"),
         _step("step-3", "lookup", depends_on=["step-1", "step-2"])],
    )
    _, _, _, scheduler = wire(stack, plan, with_plan_execution=False)

    assert scheduler.schedule("plan-1") == ["step-1", "step-2"]


def test_cancellation_stops_scheduling_even_when_steps_remain_ready():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, plan_execution, dependencies, scheduler = wire(stack, plan)
    execution = interrupt_after_first_step(plan_execution)

    assert execution.status == "CANCELLED"
    # Commit #8 alone still sees step-2 as dependency-ready (step-1 succeeded)...
    assert dependencies.ready_steps(execution.execution_id) == ["step-2"]
    # ...but the scheduler must refuse to hand it out: the run was cancelled.
    assert scheduler.schedule(execution.execution_id) == []
    assert scheduler.next_step(execution.execution_id) is None


def test_scheduling_never_executes_a_tool():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    step_execution, _, _, scheduler = wire(stack, plan, with_plan_execution=False)
    before = stack["registry"].list()

    scheduler.schedule("plan-1")
    scheduler.next_step("plan-1")
    scheduler.ready("plan-1")

    assert step_execution.executions("plan-1") == []
    assert stack["registry"].list() == before
