import threading
import time
from datetime import datetime, timezone

import pytest

from backend.agent_checkpointing import LLMAgentCheckpointService
from backend.agent_dependency_resolution import LLMAgentDependencyService, UnknownDependencyStepError
from backend.agent_execution_recovery import LLMAgentRecoveryService
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


def always_fails(topic):
    raise RuntimeError("upstream lookup service is down")


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
    """Point Commit #2/#3/#4/#5/#6/#8 at a directly-built plan sharing one stack's tools."""
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    plan_execution = LLMAgentPlanExecutionService(store, validation_service, step_execution)
    checkpoints = LLMAgentCheckpointService(store, validation_service, step_execution, plan_execution)
    recovery = LLMAgentRecoveryService(store, validation_service, step_execution, plan_execution, checkpoints)
    # Most tests drive steps directly through Commit #3 (no Commit #4
    # execution wrapper ever created), so this is built without
    # plan_execution_service -- execution_id is then just the plan_id.
    dependencies = LLMAgentDependencyService(store, step_execution)
    return step_execution, plan_execution, checkpoints, recovery, dependencies


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


def test_linear_dependencies():
    stack = build()
    plan = _plan(
        "plan-1",
        [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"]),
         _step("step-3", "lookup", depends_on=["step-2"])],
    )
    step_execution, _, _, _, dependencies = wire(stack, plan)

    assert dependencies.ready_steps("plan-1") == ["step-1"]
    assert dependencies.blocked_steps("plan-1") == ["step-2", "step-3"]

    step_execution.execute_step("plan-1", "step-1", "user:ada")
    assert dependencies.ready_steps("plan-1") == ["step-2"]
    assert dependencies.blocked_steps("plan-1") == ["step-3"]

    step_execution.execute_step("plan-1", "step-2", "user:ada")
    assert dependencies.ready_steps("plan-1") == ["step-3"]
    assert dependencies.blocked_steps("plan-1") == []


def test_parallel_ready_steps():
    stack = build()
    plan = _plan(
        "plan-1",
        [_step("step-1", "lookup"), _step("step-2", "lookup"),
         _step("step-3", "lookup", depends_on=["step-1", "step-2"])],
    )
    _, _, _, _, dependencies = wire(stack, plan)

    assert dependencies.ready_steps("plan-1") == ["step-1", "step-2"]
    assert dependencies.blocked_steps("plan-1") == ["step-3"]
    assert dependencies.can_execute("plan-1", "step-1") is True
    assert dependencies.can_execute("plan-1", "step-3") is False


def test_blocked_dependency_not_yet_attempted():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"])])
    _, _, _, _, dependencies = wire(stack, plan)

    assert dependencies.can_execute("plan-1", "step-2") is False
    assert "step-2" in dependencies.blocked_steps("plan-1")


def test_failed_dependency_blocks_downstream_permanently():
    stack = build(tools={"broken": always_fails, "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "broken"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, _, _, _, dependencies = wire(stack, plan)

    step_execution.execute_step("plan-1", "step-1", "user:ada")

    assert dependencies.ready_steps("plan-1") == []
    assert set(dependencies.blocked_steps("plan-1")) == {"step-1", "step-2"}
    assert dependencies.can_execute("plan-1", "step-2") is False


def test_completed_step_exclusion():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    step_execution, _, _, _, dependencies = wire(stack, plan)

    step_execution.execute_step("plan-1", "step-1", "user:ada")

    assert dependencies.ready_steps("plan-1") == []
    assert dependencies.blocked_steps("plan-1") == []


def test_cycle_detection_defensive():
    stack = build()
    plan = _plan(
        "plan-1",
        [_step("step-1", "lookup", depends_on=["step-2"]), _step("step-2", "lookup", depends_on=["step-1"])],
    )
    _, _, _, _, dependencies = wire(stack, plan)

    assert dependencies.ready_steps("plan-1") == []
    assert set(dependencies.blocked_steps("plan-1")) == {"step-1", "step-2"}
    assert dependencies.can_execute("plan-1", "step-1") is False


def test_deterministic_ordering_follows_plan_declaration():
    stack = build()
    # Declared in reverse -- both are independently ready, order must
    # follow declaration, not id sorting.
    plan = _plan("plan-1", [_step("step-b", "lookup"), _step("step-a", "lookup")])
    _, _, _, _, dependencies = wire(stack, plan)

    assert dependencies.ready_steps("plan-1") == ["step-b", "step-a"]


def test_dependencies_reads_the_plans_own_declaration():
    stack = build()
    plan = _plan(
        "plan-1",
        [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"])],
    )
    _, _, _, _, dependencies = wire(stack, plan)

    assert dependencies.dependencies("plan-1", "step-2") == ["step-1"]
    assert dependencies.dependencies("plan-1", "step-1") == []

    with pytest.raises(UnknownDependencyStepError):
        dependencies.dependencies("plan-1", "no-such-step")


def test_recovery_integration():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan(
        "plan-1",
        [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"]),
         _step("step-3", "lookup", depends_on=["step-2"])],
    )
    step_execution, plan_execution, checkpoints, recovery, dependencies = wire(stack, plan)
    execution = interrupt_after_first_step(plan_execution)
    checkpoints.save(execution.execution_id)

    assert dependencies.ready_steps("plan-1") == ["step-2"]
    assert dependencies.blocked_steps("plan-1") == ["step-3"]

    recovery.recover(execution.execution_id, subject="user:ada")

    assert dependencies.ready_steps("plan-1") == []
    assert dependencies.blocked_steps("plan-1") == []


def test_resolves_execution_id_through_commit4_when_wired():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"])])
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    plan_execution = LLMAgentPlanExecutionService(store, validation_service, step_execution)
    dependencies = LLMAgentDependencyService(store, step_execution, plan_execution)

    execution = plan_execution.execute("plan-1", "user:ada")

    # A fully SUCCEEDED plan has nothing left ready or blocked.
    assert dependencies.ready_steps(execution.execution_id) == []
    assert dependencies.blocked_steps(execution.execution_id) == []
    assert dependencies.dependencies(execution.execution_id, "step-2") == ["step-1"]
