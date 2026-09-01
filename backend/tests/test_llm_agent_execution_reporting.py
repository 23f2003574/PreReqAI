import time
from datetime import datetime, timezone

import pytest

from backend.agent_checkpointing import LLMAgentCheckpointService
from backend.agent_dependency_resolution import LLMAgentDependencyService
from backend.agent_execution_budget import LLMAgentExecutionBudgetService
from backend.agent_execution_reporting import LLMAgentExecutionReportService
from backend.agent_failure_handling import LLMAgentFailureService
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


def _step(step_id, tool_name, depends_on=(), arguments=None):
    return LLMAgentPlanStep(
        step_id=step_id,
        action=f"call {tool_name}",
        tool_name=tool_name,
        arguments=arguments or {"topic": "linear algebra"},
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

    return {
        "registry": registry, "invocation": invocation, "permissions": permissions,
        "orchestrator": orchestrator, "retry": retry,
    }


def wire(stack, plan, budget_service=None):
    """Point Commit #2/#3/#4/#5/#8/#9/#12 at a directly-built plan sharing one stack's tools."""
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    plan_execution = LLMAgentPlanExecutionService(store, validation_service, step_execution)
    checkpoints = LLMAgentCheckpointService(store, validation_service, step_execution, plan_execution)
    dependencies = LLMAgentDependencyService(store, step_execution)
    failures = LLMAgentFailureService(store, step_execution, stack["retry"])
    report = LLMAgentExecutionReportService(
        store, step_execution, failures, dependencies,
        checkpoint_service=checkpoints, budget_service=budget_service,
    )
    return step_execution, plan_execution, checkpoints, report


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


def test_completed_execution_report():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, _, _, report = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")
    step_execution.execute_step("plan-1", "step-2", "user:ada")

    generated = report.generate("plan-1")

    assert generated["status"] == "SUCCEEDED"
    assert generated["completed_steps"] == ["step-1", "step-2"]
    assert generated["failed_steps"] == []
    assert generated["blocked_steps"] == []
    assert [entry["step_id"] for entry in generated["steps"]] == ["step-1", "step-2"]
    assert all(entry["completed_at"] is not None for entry in generated["timings"])


def test_partial_execution_report():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, _, _, report = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")

    generated = report.generate("plan-1")

    assert generated["status"] == "IN_PROGRESS"
    assert generated["completed_steps"] == ["step-1"]
    assert generated["failed_steps"] == []
    assert generated["blocked_steps"] == []
    step2 = next(entry for entry in generated["steps"] if entry["step_id"] == "step-2")
    assert step2["status"] == "NOT_ATTEMPTED"


def test_failed_step_report():
    stack = build(tools={"broken": always_fails})
    plan = _plan("plan-1", [_step("step-1", "broken")])
    step_execution, _, _, report = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")

    generated = report.generate("plan-1")

    assert generated["status"] == "FAILED"
    assert generated["failed_steps"] == ["step-1"]
    failure = generated["failures"][0]
    assert failure["step_id"] == "step-1"
    assert failure["category"] == "PERMANENT"
    step1 = generated["steps"][0]
    assert step1["status"] == "FAILED"
    assert "upstream lookup service is down" in step1["error"]
    assert step1["output"] is None


def test_blocked_dependency_report():
    stack = build(tools={"broken": always_fails, "lookup": ok})
    plan = _plan("plan-1", [_step("step-1", "broken"), _step("step-2", "lookup", depends_on=["step-1"])])
    step_execution, _, _, report = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")

    generated = report.generate("plan-1")

    assert generated["blocked_steps"] == ["step-2"]
    assert generated["failed_steps"] == ["step-1"]
    blocked_failure = next(f for f in generated["failures"] if f["step_id"] == "step-2")
    assert blocked_failure["category"] == "DEPENDENCY_FAILURE"


def test_budget_exhaustion_report():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    budgets = LLMAgentExecutionBudgetService()
    budgets.configure("plan-1", max_steps=1)
    step_execution, _, _, report = wire(stack, plan, budget_service=budgets)
    step_execution.execute_step("plan-1", "step-1", "user:ada")
    budgets.consume("plan-1", {"steps": 1})

    generated = report.generate("plan-1")

    assert generated["budget_usage"]["configured"] is True
    assert generated["budget_usage"]["state"] == "BUDGET_EXCEEDED"
    assert generated["budget_usage"]["usage"]["steps"] == 1


def test_budget_not_configured_reports_as_unconfigured():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup")])
    step_execution, _, _, report = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")

    generated = report.generate("plan-1")

    assert generated["budget_usage"] == {"configured": False}


def test_checkpoint_inclusion():
    stack = build()
    plan = _plan("plan-1", [_step("step-1", "lookup"), _step("step-2", "lookup", depends_on=["step-1"])])
    store = FixedPlanStore(plan)
    validation_service = LLMAgentPlanValidationService(
        store, stack["registry"], stack["permissions"], invocation_service=stack["invocation"]
    )
    step_execution = LLMAgentExecutionService(store, validation_service, stack["orchestrator"])
    plan_execution = LLMAgentPlanExecutionService(store, validation_service, step_execution)
    checkpoints = LLMAgentCheckpointService(store, validation_service, step_execution, plan_execution)
    dependencies = LLMAgentDependencyService(store, step_execution, plan_execution)
    failures = LLMAgentFailureService(store, step_execution, stack["retry"], plan_execution)
    # Wired with plan_execution_service this time, so execution_id resolves
    # to Commit #4's own id -- the same id checkpoints are keyed by.
    report = LLMAgentExecutionReportService(
        store, step_execution, failures, dependencies,
        checkpoint_service=checkpoints, plan_execution_service=plan_execution,
    )

    execution = plan_execution.execute("plan-1", "user:ada")
    checkpoints.save(execution.execution_id)

    generated = report.generate(execution.execution_id)

    assert len(generated["checkpoints"]) == 1
    checkpoint = generated["checkpoints"][0]
    assert checkpoint["execution_id"] == execution.execution_id
    assert checkpoint["state"] == "SUCCEEDED"
    assert [entry["step_id"] for entry in checkpoint["completed_steps"]] == ["step-1", "step-2"]


def test_timeline_ordering_reflects_actual_completion_time_not_declaration():
    stack = build()
    # Declared with step-b first, but step-a runs (and completes) first.
    plan = _plan("plan-1", [_step("step-b", "lookup", depends_on=["step-a"]), _step("step-a", "lookup")])
    step_execution, _, checkpoints, report = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-a", "user:ada")
    step_execution.execute_step("plan-1", "step-b", "user:ada")

    timeline = report.timeline("plan-1")

    assert [event["step_id"] for event in timeline] == ["step-a", "step-b"]
    assert timeline[0]["at"] <= timeline[1]["at"]


def test_secret_exclusion_from_step_arguments():
    stack = build()
    plan = _plan(
        "plan-1",
        [_step("step-1", "lookup", arguments={"topic": "x", "api_key": "sk-abcdefghijklmnopqrstuvwx"})],
    )
    step_execution, _, _, report = wire(stack, plan)
    step_execution.execute_step("plan-1", "step-1", "user:ada")

    generated = report.generate("plan-1")

    rendered = repr(generated)
    assert "sk-abcdefghijklmnopqrstuvwx" not in rendered
    assert "[REDACTED]" in generated["steps"][0]["arguments"]["api_key"]
