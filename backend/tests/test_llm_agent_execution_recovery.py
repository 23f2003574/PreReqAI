import threading
import time
from datetime import datetime, timezone

import pytest

from backend.agent_checkpointing import InvalidCheckpointError, LLMAgentCheckpoint, LLMAgentCheckpointService
from backend.agent_execution_recovery import InconsistentCheckpointError, LLMAgentRecoveryService
from backend.agent_plan_execution import LLMAgentPlanExecutionService
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
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


class FixedPlanStore:
    def __init__(self, plan: LLMAgentPlan):
        self._plan = plan

    def get(self, plan_id: str) -> LLMAgentPlan:
        if plan_id != self._plan.plan_id:
            raise KeyError(plan_id)
        return self._plan


class FixedCheckpointStore:
    """A minimal stand-in for LLMAgentCheckpointService exposing only latest().

    Feeds the recovery service a checkpoint whose completed_steps claims
    something Commit #3's real records do not support -- corruption
    Commit #5's own save() would never itself produce, so this is the only
    way to exercise Commit #6's cross-check in isolation.
    """

    def __init__(self, checkpoint: LLMAgentCheckpoint):
        self._checkpoint = checkpoint

    def latest(self, execution_id: str) -> LLMAgentCheckpoint:
        if execution_id != self._checkpoint.execution_id:
            raise KeyError(execution_id)
        return self._checkpoint

    def resume(self, *args, **kwargs):
        raise AssertionError("resume() must never be called for a checkpoint that fails verification")


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
    return validation_service, step_execution, plan_execution, checkpoints, recovery


def interrupt_after_first_step(plan_execution, plan_id="plan-1"):
    """Runs execute() in a background thread and cancels it once the first
    (slow) step has succeeded but before the next one starts -- the same
    deterministic technique Commit #5's own tests use."""
    outcome = {}

    def run():
        outcome["execution"] = plan_execution.execute(plan_id, "user:ada")

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.02)  # well before the first step's 0.15s handler returns
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


def test_clean_recovery():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    _, step_execution, plan_execution, checkpoints, recovery = wire(stack, plan)
    execution = interrupt_after_first_step(plan_execution)
    checkpoints.save(execution.execution_id)

    result = recovery.recover(execution.execution_id, subject="user:ada")

    assert result.state == SUCCEEDED
    assert [entry["step_id"] for entry in result.completed_steps] == ["step-1", "step-2"]
    assert len(step_execution.executions("plan-1")) == 2


def test_partial_execution_recovery_completes_a_longer_chain():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan(
        "plan-1",
        [
            _step("step-1", "slow"),
            _step("step-2", "lookup", depends_on=["step-1"]),
            _step("step-3", "lookup", depends_on=["step-2"]),
        ],
    )
    _, step_execution, plan_execution, checkpoints, recovery = wire(stack, plan)
    execution = interrupt_after_first_step(plan_execution)
    checkpoints.save(execution.execution_id)

    assert recovery.remaining_steps(execution.execution_id) == ["step-2", "step-3"]

    result = recovery.recover(execution.execution_id, subject="user:ada")

    assert result.state == SUCCEEDED
    assert [entry["step_id"] for entry in result.completed_steps] == ["step-1", "step-2", "step-3"]


def test_completed_step_skipping_preserves_the_original_execution_id():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    _, step_execution, plan_execution, checkpoints, recovery = wire(stack, plan)
    execution = interrupt_after_first_step(plan_execution)
    checkpoint = checkpoints.save(execution.execution_id)
    original_step1_execution_id = checkpoint.completed_steps[0]["execution_id"]

    result = recovery.recover(execution.execution_id, subject="user:ada")

    assert result.completed_steps[0]["execution_id"] == original_step1_execution_id
    records = step_execution.executions("plan-1")
    assert len([r for r in records if r.step_id == "step-1"]) == 1
    assert records[0].execution_id == original_step1_execution_id


def test_dependency_safe_resume_runs_in_dependency_order():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    # step-1 declared last, but everything depends on it transitively.
    plan = _plan(
        "plan-1",
        [
            _step("step-3", "lookup", depends_on=["step-2"]),
            _step("step-2", "lookup", depends_on=["step-1"]),
            _step("step-1", "slow"),
        ],
    )
    _, step_execution, plan_execution, checkpoints, recovery = wire(stack, plan)
    execution = interrupt_after_first_step(plan_execution)
    checkpoints.save(execution.execution_id)

    assert recovery.remaining_steps(execution.execution_id) == ["step-2", "step-3"]

    result = recovery.recover(execution.execution_id, subject="user:ada")

    assert [entry["step_id"] for entry in result.completed_steps] == ["step-1", "step-2", "step-3"]
    recorded_order = [r.step_id for r in step_execution.executions("plan-1")]
    assert recorded_order == ["step-1", "step-2", "step-3"]


def test_invalid_checkpoint_cannot_be_recovered():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    _, _, plan_execution, checkpoints, recovery = wire(stack, plan)
    execution = plan_execution.execute("plan-1", "user:ada")
    checkpoints.save(execution.execution_id)  # state SUCCEEDED -- nothing to recover

    assert recovery.validate_checkpoint(execution.execution_id) is False
    with pytest.raises(InvalidCheckpointError):
        recovery.recover(execution.execution_id, subject="user:ada")


def test_inconsistent_execution_state_missing_record():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    _, step_execution, plan_execution, checkpoints, _ = wire(stack, plan)
    execution = interrupt_after_first_step(plan_execution)

    corrupted = LLMAgentCheckpoint(
        checkpoint_id="fake-checkpoint-1",
        execution_id=execution.execution_id,
        completed_steps=({"step_id": "step-1", "execution_id": "no-such-execution"},),
        current_step="step-2",
        state="CANCELLED",
        created_at=datetime.now(timezone.utc),
    )
    validation_service = LLMAgentPlanValidationService(
        FixedPlanStore(plan), stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    recovery = LLMAgentRecoveryService(
        FixedPlanStore(plan), validation_service, step_execution, plan_execution, FixedCheckpointStore(corrupted)
    )

    assert recovery.validate_checkpoint(execution.execution_id) is False
    with pytest.raises(InconsistentCheckpointError):
        recovery.recover(execution.execution_id, subject="user:ada")
    with pytest.raises(InconsistentCheckpointError):
        recovery.remaining_steps(execution.execution_id)


def test_inconsistent_execution_state_status_mismatch():
    stack = build(tools={"broken": always_fails, "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "broken"), _step("step-2", "lookup", depends_on=["step-1"])])
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    plan_execution = LLMAgentPlanExecutionService(store, validation_service, step_execution)

    # A real, but FAILED, execution -- the checkpoint below lies and claims
    # it as the completed step-1.
    execution = plan_execution.execute("plan-1", "user:ada")
    assert execution.status == FAILED
    failed_execution_id = step_execution.executions("plan-1")[0].execution_id

    corrupted = LLMAgentCheckpoint(
        checkpoint_id="fake-checkpoint-1",
        execution_id=execution.execution_id,
        completed_steps=({"step_id": "step-1", "execution_id": failed_execution_id},),
        current_step="step-2",
        state="CANCELLED",
        created_at=datetime.now(timezone.utc),
    )
    recovery = LLMAgentRecoveryService(
        store, validation_service, step_execution, plan_execution, FixedCheckpointStore(corrupted)
    )

    assert recovery.validate_checkpoint(execution.execution_id) is False
    with pytest.raises(InconsistentCheckpointError):
        recovery.recover(execution.execution_id, subject="user:ada")


def test_recovery_after_failure_reports_failed_not_successful():
    stack = build(tools={"slow": make_slow(0.15), "broken": always_fails})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "broken", depends_on=["step-1"])])
    _, step_execution, plan_execution, checkpoints, recovery = wire(stack, plan)
    execution = interrupt_after_first_step(plan_execution)
    checkpoints.save(execution.execution_id)

    result = recovery.recover(execution.execution_id, subject="user:ada")

    assert result.state == FAILED
    assert [entry["step_id"] for entry in result.completed_steps] == ["step-1"]


def test_recovery_idempotency_does_not_duplicate_work():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "slow"), _step("step-2", "lookup", depends_on=["step-1"])])
    _, step_execution, plan_execution, checkpoints, recovery = wire(stack, plan)
    execution = interrupt_after_first_step(plan_execution)
    checkpoints.save(execution.execution_id)

    first = recovery.recover(execution.execution_id, subject="user:ada")
    assert first.state == SUCCEEDED
    records_after_first = step_execution.executions("plan-1")

    with pytest.raises(InvalidCheckpointError):
        recovery.recover(execution.execution_id, subject="user:ada")

    assert step_execution.executions("plan-1") == records_after_first
