import threading
import time
from datetime import datetime, timezone

import pytest

from backend.agent_checkpointing import (
    InvalidCheckpointError,
    LLMAgentCheckpointService,
    UnknownCheckpointError,
)
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.tool_audit import LLMToolAuditService
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import LLMToolExecutionService, SUCCEEDED
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
    """Point Commit #2/#3/#4/#5 at a directly-built plan sharing one stack's tools."""
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    plan_execution = LLMAgentPlanExecutionService(store, validation_service, step_execution)
    checkpoints = LLMAgentCheckpointService(store, validation_service, step_execution, plan_execution)
    return validation_service, step_execution, plan_execution, checkpoints


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


def test_checkpoint_creation_after_a_successful_run():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, step_execution, plan_execution, checkpoints = wire(stack, plan)

    execution = plan_execution.execute("plan-1", "user:ada")
    checkpoint = checkpoints.save(execution.execution_id)

    assert checkpoint.execution_id == execution.execution_id
    assert checkpoint.state == SUCCEEDED
    assert checkpoint.current_step is None
    step_record = step_execution.executions("plan-1")[0]
    assert checkpoint.completed_steps == ({"step_id": "step-1", "execution_id": step_record.execution_id},)
    assert checkpoint.created_at is not None


def test_latest_checkpoint_is_the_most_recent_one_saved():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"])])
    _, step_execution, plan_execution, checkpoints = wire(stack, plan)
    execution = plan_execution.execute("plan-1", "user:ada")

    first = checkpoints.save(execution.execution_id)
    second = checkpoints.save(execution.execution_id)

    assert first.checkpoint_id != second.checkpoint_id
    assert checkpoints.latest(execution.execution_id) == second


def test_interrupted_execution_is_captured_by_cancellation():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    _, step_execution, plan_execution, checkpoints = wire(stack, plan)
    outcome = {}

    def run():
        outcome["execution"] = plan_execution.execute("plan-1", "user:ada")

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.02)  # well before step-1's 0.15s handler returns
    plan_execution.cancel("agent-plan-execution-1")
    worker.join(timeout=5)

    assert outcome["execution"].status == "CANCELLED"
    assert outcome["execution"].completed_steps == ["step-1"]

    checkpoint = checkpoints.save(outcome["execution"].execution_id)

    assert checkpoint.state == "CANCELLED"
    assert checkpoint.current_step == "step-2"
    assert [entry["step_id"] for entry in checkpoint.completed_steps] == ["step-1"]
    # Only one step ever ran -- step-2 was never attempted before the interruption.
    assert len(step_execution.executions("plan-1")) == 1


def test_resume_completes_the_remaining_steps():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    _, step_execution, plan_execution, checkpoints = wire(stack, plan)
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

    resumed = checkpoints.resume(execution_id, subject="user:ada")

    assert resumed.state == SUCCEEDED
    assert resumed.current_step is None
    assert [entry["step_id"] for entry in resumed.completed_steps] == ["step-1", "step-2"]
    assert len(step_execution.executions("plan-1")) == 2
    assert checkpoints.latest(execution_id) == resumed


def test_completed_step_preservation_across_resume():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    _, step_execution, plan_execution, checkpoints = wire(stack, plan)
    outcome = {}

    def run():
        outcome["execution"] = plan_execution.execute("plan-1", "user:ada")

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.02)
    plan_execution.cancel("agent-plan-execution-1")
    worker.join(timeout=5)
    execution_id = outcome["execution"].execution_id
    checkpoint_before = checkpoints.save(execution_id)
    step1_execution_id = checkpoint_before.completed_steps[0]["execution_id"]

    resumed = checkpoints.resume(execution_id, subject="user:ada")

    # The exact same Commit #3 record for step-1 is still the one referenced --
    # it was never touched, let alone rerun.
    assert resumed.completed_steps[0]["execution_id"] == step1_execution_id
    preserved = step_execution.get(step1_execution_id)
    assert preserved.status == SUCCEEDED


def test_no_duplicate_step_execution_on_resume():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    _, step_execution, plan_execution, checkpoints = wire(stack, plan)
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

    checkpoints.resume(execution_id, subject="user:ada")

    records = step_execution.executions("plan-1")
    step_ids = [record.step_id for record in records]
    assert sorted(step_ids) == ["step-1", "step-2"]  # exactly one record per step
    assert len(records) == 2


def test_invalid_checkpoint_unknown_execution_raises():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, _, _, checkpoints = wire(stack, plan)

    with pytest.raises(UnknownCheckpointError):
        checkpoints.latest("no-such-execution")
    with pytest.raises(UnknownCheckpointError):
        checkpoints.resume("no-such-execution", subject="user:ada")


def test_invalid_checkpoint_cannot_resume_a_succeeded_plan():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, _, plan_execution, checkpoints = wire(stack, plan)
    execution = plan_execution.execute("plan-1", "user:ada")
    checkpoints.save(execution.execution_id)

    with pytest.raises(InvalidCheckpointError):
        checkpoints.resume(execution.execution_id, subject="user:ada")
