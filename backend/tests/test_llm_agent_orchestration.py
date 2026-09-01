import json
import threading
import time

import pytest

from backend.agent_checkpointing import LLMAgentCheckpointService
from backend.agent_dependency_resolution import LLMAgentDependencyService
from backend.agent_execution_budget import LLMAgentExecutionBudgetService
from backend.agent_execution_context import LLMAgentExecutionContextService
from backend.agent_execution_recovery import LLMAgentRecoveryService
from backend.agent_execution_reporting import LLMAgentExecutionReportService
from backend.agent_failure_handling import LLMAgentFailureService
from backend.agent_orchestration import LLMAgentOrchestrationService
from backend.agent_plan_execution import LLMAgentPlanExecutionService, PlanExecutionAlreadyExistsError
from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_step_execution import LLMAgentExecutionService
from backend.agent_task_planning import LLMAgentPlanningService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.retry import TransientLLMError
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
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


def flaky(failures, error_factory):
    calls = {"count": 0}

    def handler(topic):
        calls["count"] += 1
        if calls["count"] <= failures:
            raise error_factory()
        return {"topic": topic, "found": True}

    return handler


class ScriptedProvider(LLMProvider):
    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request):
        raise NotImplementedError


def make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


TWO_STEP_PLAN = json.dumps(
    {
        "steps": [
            {"action": "Find prerequisites", "tool": "lookup", "arguments": {"topic": "linear algebra"}, "depends_on": []},
            {"action": "Summarize findings", "tool": "lookup", "arguments": {"topic": "summary"}, "depends_on": [0]},
        ]
    }
)

INVALID_TOOL_PLAN = json.dumps(
    {"steps": [{"action": "Use a tool that does not exist", "tool": "no_such_tool", "arguments": {}, "depends_on": []}]}
)


def build(tools=None, script=None):
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
        control, execution, LLMToolRetryPolicy(max_attempts=2, backoff=0.0),
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

    llm_config = LLMProviderConfigService()
    llm_config.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True)
    )
    routing = LLMModelRoutingService(llm_config)
    routing.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )
    llm_context = LLMContextService()
    llm_provider = ScriptedProvider(script or [make_response(TWO_STEP_PLAN)])
    llm_orchestration = LLMRequestOrchestrationService(
        context_service=llm_context, routing_service=routing, providers={"openai": llm_provider},
    )

    planning = LLMAgentPlanningService(registry, llm_orchestration, llm_context)
    validation = LLMAgentPlanValidationService(planning, registry, permissions, invocation_service=invocation)
    step_execution = LLMAgentExecutionService(planning, validation, orchestrator)
    plan_execution = LLMAgentPlanExecutionService(planning, validation, step_execution)
    checkpoints = LLMAgentCheckpointService(planning, validation, step_execution, plan_execution)
    recovery = LLMAgentRecoveryService(planning, validation, step_execution, plan_execution, checkpoints)
    agent_context = LLMAgentExecutionContextService(planning, step_execution)
    dependencies = LLMAgentDependencyService(planning, step_execution, plan_execution)
    failures = LLMAgentFailureService(planning, step_execution, retry, plan_execution)
    budgets = LLMAgentExecutionBudgetService()
    report = LLMAgentExecutionReportService(
        planning, step_execution, failures, dependencies,
        checkpoint_service=checkpoints, budget_service=budgets, plan_execution_service=plan_execution,
    )

    agent = LLMAgentOrchestrationService(
        planning, validation, step_execution, plan_execution, checkpoints, recovery, report,
        dependency_service=dependencies, context_service=agent_context, budget_service=budgets,
    )

    return {
        "registry": registry, "permissions": permissions, "step_execution": step_execution,
        "plan_execution": plan_execution, "checkpoints": checkpoints, "agent_context": agent_context,
        "budgets": budgets, "agent": agent,
    }


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


def test_successful_multi_step_workflow():
    stack = build()
    agent = stack["agent"]

    plan = agent.create_plan("Learn linear algebra")
    assert agent.validate(plan.plan_id) == []

    execution = agent.execute(plan.plan_id, "user:ada")

    assert execution.status == "SUCCEEDED"
    assert execution.completed_steps == [plan.steps[0].step_id, plan.steps[1].step_id]
    for step in plan.steps:
        assert stack["agent_context"].for_step(execution.execution_id, step.step_id) is not None


def test_validation_rejection():
    stack = build(script=[make_response(INVALID_TOOL_PLAN)])
    agent = stack["agent"]

    plan = agent.create_plan("Do something unsupported")
    findings = agent.validate(plan.plan_id)

    assert len(findings) == 1
    assert findings[0].category == "UNKNOWN_TOOL"

    execution = agent.execute(plan.plan_id, "user:ada")

    assert execution.status == "REJECTED"
    assert execution.completed_steps == []
    assert stack["step_execution"].executions(plan.plan_id) == []


def test_dependency_failure_stops_the_workflow():
    stack = build(
        tools={"broken": always_fails, "lookup": ok},
        script=[
            make_response(
                json.dumps(
                    {
                        "steps": [
                            {"action": "a", "tool": "broken", "arguments": {"topic": "x"}, "depends_on": []},
                            {"action": "b", "tool": "lookup", "arguments": {"topic": "x"}, "depends_on": [0]},
                        ]
                    }
                )
            )
        ],
    )
    agent = stack["agent"]
    plan = agent.create_plan("A task with a failing dependency")

    execution = agent.execute(plan.plan_id, "user:ada")

    assert execution.status == "FAILED"
    assert execution.failed_step == plan.steps[0].step_id
    assert execution.completed_steps == []

    generated = agent.report(execution.execution_id)
    assert generated["failed_steps"] == [plan.steps[0].step_id]
    assert generated["blocked_steps"] == [plan.steps[1].step_id]


def test_tool_failure_with_retry_eventually_succeeds():
    stack = build(
        tools={"flaky": flaky(1, lambda: TransientLLMError("brief outage"))},
        script=[
            make_response(
                json.dumps(
                    {"steps": [{"action": "a", "tool": "flaky", "arguments": {"topic": "x"}, "depends_on": []}]}
                )
            )
        ],
    )
    agent = stack["agent"]
    plan = agent.create_plan("A task whose tool briefly fails")

    execution = agent.execute(plan.plan_id, "user:ada")

    assert execution.status == "SUCCEEDED"


def test_budget_exhaustion_stops_the_workflow():
    stack = build(script=[make_response(TWO_STEP_PLAN)])
    agent = stack["agent"]
    plan = agent.create_plan("Learn linear algebra")

    execution = agent.execute(plan.plan_id, "user:ada", budget={"max_steps": 1})

    assert execution.status == "CANCELLED"
    assert execution.completed_steps == [plan.steps[0].step_id]
    generated = agent.report(execution.execution_id)
    assert generated["budget_usage"]["state"] == "BUDGET_EXCEEDED"


def test_timeout_and_cancellation():
    stack = build(tools={"slow": make_slow(0.2)}, script=[
        make_response(
            json.dumps(
                {
                    "steps": [
                        {"action": "a", "tool": "slow", "arguments": {"topic": "x"}, "depends_on": []},
                        {"action": "b", "tool": "slow", "arguments": {"topic": "x"}, "depends_on": [0]},
                    ]
                }
            )
        )
    ])
    agent = stack["agent"]
    plan = agent.create_plan("A slow task")
    outcome = {}

    def run():
        outcome["execution"] = agent.execute(plan.plan_id, "user:ada")

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.02)
    agent.cancel("agent-plan-execution-1")
    worker.join(timeout=5)

    assert outcome["execution"].status == "CANCELLED"
    assert outcome["execution"].completed_steps == [plan.steps[0].step_id]


def test_checkpoint_recovery():
    stack = build(tools={"slow": make_slow(0.15), "lookup": ok}, script=[
        make_response(
            json.dumps(
                {
                    "steps": [
                        {"action": "a", "tool": "slow", "arguments": {"topic": "x"}, "depends_on": []},
                        {"action": "b", "tool": "lookup", "arguments": {"topic": "x"}, "depends_on": [0]},
                    ]
                }
            )
        )
    ])
    agent = stack["agent"]
    plan = agent.create_plan("A task interrupted partway")
    outcome = {}

    def run():
        outcome["execution"] = agent.execute(plan.plan_id, "user:ada")

    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(0.02)
    agent.cancel("agent-plan-execution-1")
    worker.join(timeout=5)
    execution_id = outcome["execution"].execution_id
    assert outcome["execution"].status == "CANCELLED"

    resumed = agent.resume(execution_id, subject="user:ada")

    assert resumed.state == "SUCCEEDED"
    assert len(resumed.completed_steps) == 2
    assert len(stack["step_execution"].executions(plan.plan_id)) == 2


def test_context_propagation():
    stack = build(script=[make_response(TWO_STEP_PLAN)])
    agent = stack["agent"]
    plan = agent.create_plan("Learn linear algebra")

    execution = agent.execute(plan.plan_id, "user:ada")

    context_payload = stack["agent_context"].context(execution.execution_id)
    assert len(context_payload["messages"]) == 2


def test_final_report_contains_required_fields():
    stack = build(script=[make_response(TWO_STEP_PLAN)])
    agent = stack["agent"]
    plan = agent.create_plan("Learn linear algebra")

    execution = agent.execute(plan.plan_id, "user:ada")
    generated = agent.report(execution.execution_id)

    for field in ("status", "completed_steps", "failed_steps", "blocked_steps", "budget_usage", "checkpoints", "timings"):
        assert field in generated


def test_deterministic_final_state():
    stack = build(script=[make_response(TWO_STEP_PLAN)])
    agent = stack["agent"]
    plan = agent.create_plan("Learn linear algebra")

    execution = agent.execute(plan.plan_id, "user:ada")

    assert agent.report(execution.execution_id) == agent.report(execution.execution_id)
    with pytest.raises(PlanExecutionAlreadyExistsError):
        agent.execute(plan.plan_id, "user:ada")
