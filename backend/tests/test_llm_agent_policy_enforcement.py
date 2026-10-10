from datetime import datetime, timezone

import pytest

from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_enforcement import (
    LLMAgentPolicyEnforcedExecutionService,
    LLMAgentPolicyEnforcement,
    PolicyEvaluationFailedError,
    is_blocking,
)
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import DENIED, REJECTED, SUCCEEDED, LLMToolExecutionService
from backend.llm.tool_idempotency import LLMToolIdempotencyService
from backend.llm.tool_invocation import LLMToolInvocationService
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


class MultiPlanStore:
    def __init__(self):
        self._plans = {}

    def add(self, plan: LLMAgentPlan):
        self._plans[plan.plan_id] = plan

    def get(self, plan_id: str) -> LLMAgentPlan:
        return self._plans[plan_id]


def _step(step_id, tool_name):
    return LLMAgentPlanStep(
        step_id=step_id, action=f"call {tool_name}", tool_name=tool_name,
        arguments={"topic": "linear algebra"}, depends_on=[], status=READY, errors=[],
    )


def _plan(plan_id, tool_name):
    return LLMAgentPlan(
        plan_id=plan_id, task="a test task", steps=[_step("step-1", tool_name)],
        status=READY, created_at=datetime.now(timezone.utc),
    )


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _harness(tool_name="lookup", handler=None, call_count=None):
    """The exact real tool-calling pipeline
    backend/tests/test_llm_agent_strategy_library.py already builds --
    registry, invocation, tool_permissions, execution, idempotency,
    control, retry, results, orchestrator -- wired for one tool, plus a
    Commit #2 plan validation service and a MultiPlanStore, so
    execute_step() runs through the real boundary end to end."""
    store = MultiPlanStore()
    registry = LLMToolRegistryService()
    registry.register(tool_name, f"Tool {tool_name}", SCHEMA)

    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    permissions.register(
        LLMToolPermissionPolicy(policy_id="allow-1", tool_name=tool_name, subject=ANY_SUBJECT, allowed=True)
    )

    def _handler(topic):
        if call_count is not None:
            call_count["calls"] += 1
        return {"topic": topic, "found": True}

    execution = LLMToolExecutionService(registry, permissions)
    execution.bind(tool_name, handler or _handler)

    idempotency = LLMToolIdempotencyService(execution, permissions)
    control = LLMToolExecutionControlService(execution, idempotency)
    retry = LLMToolRetryService(
        control, execution, LLMToolRetryPolicy(max_attempts=1, backoff=0.0),
        sleeper=lambda seconds: None, idempotency_service=idempotency,
    )
    results = LLMToolResultService()
    orchestrator = LLMToolCallingOrchestrationService(
        invocation_service=invocation, permission_service=permissions, execution_service=execution,
        result_service=results, idempotency_service=idempotency, control_service=control,
        retry_service=retry,
    )

    validation_service = LLMAgentPlanValidationService(store, registry, permissions, invocation_service=invocation)
    return store, validation_service, orchestrator


def _enforcement(scope_id, rules):
    policy_service = LLMAgentPolicyService()
    if rules:
        policy_service.create(scope_id, "test-policy", rules)
    resolver = LLMAgentPolicyResolver(policy_service)
    return LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())


def test_allow():
    enforcement = _enforcement("notebook-1", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})])
    decision = enforcement.enforce({"scope_id": "notebook-1", "tool_name": "lookup"})

    assert decision.decision == ALLOW
    assert is_blocking(decision) is False


def test_denied_action_is_blocked_before_execution():
    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness(call_count=call_count)
    store.add(_plan("plan-1", "lookup"))

    enforcement = _enforcement("notebook-1", [_rule("deny-lookup", DENY, {"tool_name": "lookup"}, "no lookups here")])
    service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )

    result = service.execute_step("plan-1", "step-1", "user:ada")

    assert result.status == DENIED
    assert "no lookups here" in result.error
    assert call_count["calls"] == 0


def test_allowed_action_proceeds_through_real_pipeline():
    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness(call_count=call_count)
    store.add(_plan("plan-1", "lookup"))

    enforcement = _enforcement("notebook-1", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})])
    service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )

    result = service.execute_step("plan-1", "step-1", "user:ada")

    assert result.status == SUCCEEDED
    assert result.result.output == {"topic": "linear algebra", "found": True}
    assert call_count["calls"] == 1


def test_existing_behavior_unchanged_when_no_policy_exists():
    """Regression: a scope with no configured policies at all must behave
    exactly as it did before Commit #4 existed -- the action proceeds,
    it is not newly denied by default."""
    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness(call_count=call_count)
    store.add(_plan("plan-1", "lookup"))

    enforcement = _enforcement("notebook-1", rules=[])
    service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )

    result = service.execute_step("plan-1", "step-1", "user:ada")

    assert result.status == SUCCEEDED
    assert call_count["calls"] == 1


def test_policy_evaluation_failure_fails_closed():
    class ExplodingResolver:
        def resolve(self, scope_id, context=None):
            raise RuntimeError("resolver is misconfigured")

    enforcement = LLMAgentPolicyEnforcement(ExplodingResolver(), LLMAgentPolicyDecisionEngine())

    with pytest.raises(PolicyEvaluationFailedError):
        enforcement.enforce({"scope_id": "notebook-1", "tool_name": "lookup"})

    # at the real execution boundary, that same failure blocks the action
    # rather than letting it through
    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness(call_count=call_count)
    store.add(_plan("plan-1", "lookup"))

    service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )
    result = service.execute_step("plan-1", "step-1", "user:ada")

    assert result.status == DENIED
    assert "evaluation failed" in result.error
    assert call_count["calls"] == 0


def test_provenance_reaches_caller():
    enforcement = _enforcement(
        "notebook-1",
        [_rule("deny-lookup", DENY, {"tool_name": "lookup"}, "blocked for compliance reasons")],
    )
    decision = enforcement.enforce({"scope_id": "notebook-1", "tool_name": "lookup"})

    assert decision.decision == DENY
    assert decision.reasons == ["blocked for compliance reasons"]
    assert len(decision.matched_rules) == 1
    assert decision.matched_rules[0].rule_id == "deny-lookup"
    assert len(decision.provenance) == 1
    assert decision.provenance[0].decision.reason == "blocked for compliance reasons"


def test_middleware_integration_leaves_dependency_and_validation_gates_intact():
    """The base class's own pre-existing gates must still run unmodified
    through the subclass -- a step with an unsatisfied dependency is
    still REJECTED, exactly as before Commit #4."""
    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness(call_count=call_count)
    dependent_step = LLMAgentPlanStep(
        step_id="step-2", action="call lookup", tool_name="lookup",
        arguments={"topic": "linear algebra"}, depends_on=["step-1"], status=READY, errors=[],
    )
    plan = LLMAgentPlan(
        plan_id="plan-1", task="a test task",
        steps=[_step("step-1", "lookup"), dependent_step],
        status=READY, created_at=datetime.now(timezone.utc),
    )
    store.add(plan)

    enforcement = _enforcement("notebook-1", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})])
    service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )

    # step-2 depends on step-1, which has not been run yet
    result = service.execute_step("plan-1", "step-2", "user:ada")

    assert result.status == REJECTED
    assert "dependency" in result.error
    assert call_count["calls"] == 0
