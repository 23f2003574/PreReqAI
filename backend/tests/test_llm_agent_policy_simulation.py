from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcedExecutionService, LLMAgentPolicyEnforcement
from backend.agent_policy_exceptions import LLMAgentPolicyExceptionAwareDecisionEngine, LLMAgentPolicyExceptionService
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_policy_simulation import LLMAgentPolicySimulator, PolicySimulationResult
from backend.agent_task_planning import READY, LLMAgentPlan, LLMAgentPlanStep
from backend.llm.tool_control import LLMToolExecutionControlService
from backend.llm.tool_execution import DENIED, SUCCEEDED, LLMToolExecutionService
from backend.llm.tool_idempotency import LLMToolIdempotencyService
from backend.llm.tool_invocation import LLMToolInvocationService
from backend.llm.tool_orchestration import LLMToolCallingOrchestrationService
from backend.llm.tool_permissions import ANY_SUBJECT, LLMToolPermissionPolicy, LLMToolPermissionService
from backend.llm.tool_results import LLMToolResultService
from backend.llm.tool_retry import LLMToolRetryPolicy, LLMToolRetryService
from backend.llm.tools import LLMToolRegistryService

SCHEMA = {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}
FUTURE = datetime.now(timezone.utc) + timedelta(days=1)


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _simulator(scope_id, rules, exception_service=None):
    policy_service = LLMAgentPolicyService()
    created = None
    if rules:
        created = policy_service.create(scope_id, "test-policy", rules)
    resolver = LLMAgentPolicyResolver(policy_service)
    decision_engine = (
        LLMAgentPolicyExceptionAwareDecisionEngine(exception_service)
        if exception_service is not None
        else LLMAgentPolicyDecisionEngine()
    )
    enforcement = LLMAgentPolicyEnforcement(resolver, decision_engine)
    return created, LLMAgentPolicySimulator(enforcement), enforcement


def test_allowed_simulation():
    policy, simulator, _ = _simulator(
        "notebook-1", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"}, "lookup is safe")]
    )
    result = simulator.simulate({"scope_id": "notebook-1", "tool_name": "lookup"})

    assert isinstance(result, PolicySimulationResult)
    assert result.would_allow is True
    assert result.final_decision.decision == ALLOW
    assert result.matched_policies == [policy.policy_id]
    assert result.reasons == ["lookup is safe"]
    assert result.conflicts == []


def test_denied_simulation():
    policy, simulator, _ = _simulator(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    result = simulator.simulate({"scope_id": "notebook-1", "tool_name": "delete"})

    assert result.would_allow is False
    assert result.final_decision.decision == DENY
    assert result.matched_policies == [policy.policy_id]
    assert result.reasons == ["delete is blocked"]


def test_exception_override_visible_in_simulation():
    exception_service = LLMAgentPolicyExceptionService()
    policy, simulator, _ = _simulator(
        "notebook-1",
        [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")],
        exception_service=exception_service,
    )
    exception_service.create(
        "notebook-1", policy.policy_id, {"tool_name": "delete"}, "approved maintenance window", FUTURE
    )

    result = simulator.simulate({"scope_id": "notebook-1", "tool_name": "delete"})

    assert result.would_allow is True
    assert result.final_decision.decision == ALLOW
    assert len(result.applicable_exceptions) == 1
    assert result.applicable_exceptions[0].policy_id == policy.policy_id
    assert any("approved maintenance window" in reason for reason in result.reasons)


def test_policy_conflict_is_surfaced():
    policy_service = LLMAgentPolicyService()
    allow_policy = policy_service.create(
        "notebook-1", "allow-policy", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"}, "generally fine")]
    )
    deny_policy = policy_service.create(
        "notebook-1", "deny-policy", [_rule("deny-lookup", DENY, {"tool_name": "lookup"}, "blocked here")]
    )
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    simulator = LLMAgentPolicySimulator(enforcement)

    result = simulator.simulate({"scope_id": "notebook-1", "tool_name": "lookup"})

    # deny wins deterministically, but the conflict is not hidden
    assert result.would_allow is False
    assert result.final_decision.decision == DENY
    assert len(result.conflicts) == 1
    conflict = result.conflicts[0]
    assert conflict.allow.policy_id == allow_policy.policy_id
    assert conflict.deny.policy_id == deny_policy.policy_id


def test_no_policy_case():
    _, simulator, _ = _simulator("notebook-1", rules=[])
    result = simulator.simulate({"scope_id": "notebook-1", "tool_name": "lookup"})

    # existing behavior unchanged: no policy at all means the action
    # would proceed, even though the raw decision is a default DENY
    assert result.would_allow is True
    assert result.final_decision.decision == DENY
    assert result.matched_policies == []
    assert result.conflicts == []


def test_simulation_is_deterministic():
    _, simulator, _ = _simulator(
        "notebook-1", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})]
    )
    action = {"scope_id": "notebook-1", "tool_name": "lookup"}

    first = simulator.simulate(action)
    second = simulator.simulate(action)

    # simulated_at is naturally wall-clock, everything else must be identical
    assert first.would_allow == second.would_allow
    assert first.final_decision == second.final_decision
    assert first.matched_policies == second.matched_policies
    assert first.reasons == second.reasons
    assert first.conflicts == second.conflicts


def test_simulate_rejects_invalid_action_context():
    _, simulator, _ = _simulator("notebook-1", [_rule("allow-lookup", ALLOW)])
    with pytest.raises(Exception):
        simulator.simulate("not-a-dict")


# --- zero side effects + simulation/enforcement parity, against a real
# execution boundary ----------------------------------------------------


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


def _harness(tool_name, call_count):
    store = MultiPlanStore()
    registry = LLMToolRegistryService()
    registry.register(tool_name, f"Tool {tool_name}", SCHEMA)

    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    permissions.register(
        LLMToolPermissionPolicy(policy_id="allow-1", tool_name=tool_name, subject=ANY_SUBJECT, allowed=True)
    )

    def handler(topic):
        call_count["calls"] += 1
        return {"topic": topic, "found": True}

    execution = LLMToolExecutionService(registry, permissions)
    execution.bind(tool_name, handler)

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


@pytest.mark.parametrize(
    "rules, expect_allow",
    [
        ([_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})], True),
        ([_rule("deny-lookup", DENY, {"tool_name": "lookup"}, "blocked")], False),
        ([], True),  # no policy at all -- existing behavior unchanged
    ],
)
def test_simulation_enforcement_parity(rules, expect_allow):
    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness("lookup", call_count)
    store.add(_plan("plan-1", "lookup"))

    policy_service = LLMAgentPolicyService()
    if rules:
        policy_service.create("notebook-1", "policy", rules)
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    simulator = LLMAgentPolicySimulator(enforcement)

    action_context = {"scope_id": "notebook-1", "tool_name": "lookup"}
    simulated = simulator.simulate(action_context)
    assert simulated.would_allow is expect_allow
    assert call_count["calls"] == 0  # simulate() never touches real execution

    service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )
    real_result = service.execute_step("plan-1", "step-1", "user:ada")

    real_allowed = real_result.status == SUCCEEDED
    assert real_allowed is expect_allow
    if expect_allow:
        assert real_result.status == SUCCEEDED
        assert call_count["calls"] == 1
    else:
        assert real_result.status == DENIED
        assert call_count["calls"] == 0

    # the simulation itself never caused any of the real execution's
    # side effects
    assert simulated.would_allow == real_allowed


def test_zero_side_effects_repeated_simulation():
    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness("lookup", call_count)
    store.add(_plan("plan-1", "lookup"))

    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "notebook-1", "policy", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})]
    )
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    simulator = LLMAgentPolicySimulator(enforcement)

    action_context = {"scope_id": "notebook-1", "tool_name": "lookup"}
    for _ in range(5):
        simulator.simulate(action_context)

    assert call_count["calls"] == 0
    assert len(policy_service.list("notebook-1")) == 1  # unmutated

    # a real call still works afterward, unaffected by the simulations
    service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )
    result = service.execute_step("plan-1", "step-1", "user:ada")
    assert result.status == SUCCEEDED
    assert call_count["calls"] == 1
