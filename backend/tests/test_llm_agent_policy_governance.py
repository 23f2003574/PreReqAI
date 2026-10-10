from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_policy_audit import LLMAgentPolicyAuditedExecutionService, LLMAgentPolicyAuditService
from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement, PolicyEvaluationFailedError
from backend.agent_policy_exceptions import LLMAgentPolicyExceptionAwareDecisionEngine, LLMAgentPolicyExceptionService
from backend.agent_policy_governance import (
    GovernanceResult,
    LLMAgentPolicyGovernanceOrchestrator,
    NoExecutionBoundaryConfiguredError,
)
from backend.agent_policy_resolution import LLMAgentPolicyResolver
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


def _build(tool_name="lookup", call_count=None, exception_service=None):
    call_count = call_count if call_count is not None else {"calls": 0}
    store, validation_service, tool_orchestrator = _harness(tool_name, call_count)

    policy_service = LLMAgentPolicyService()
    resolver = LLMAgentPolicyResolver(policy_service)
    decision_engine = (
        LLMAgentPolicyExceptionAwareDecisionEngine(exception_service)
        if exception_service is not None
        else LLMAgentPolicyDecisionEngine()
    )
    enforcement = LLMAgentPolicyEnforcement(resolver, decision_engine)
    audit_service = LLMAgentPolicyAuditService()

    execution_service = LLMAgentPolicyAuditedExecutionService(
        store, validation_service, tool_orchestrator, enforcement,
        scope_for_plan=lambda plan_id: "notebook-1", audit_service=audit_service,
    )

    orchestrator_service = LLMAgentPolicyGovernanceOrchestrator(
        enforcement=enforcement, audit_service=audit_service, execution_service=execution_service,
    )
    return policy_service, audit_service, orchestrator_service, store, call_count


def test_full_allow_flow():
    policy_service, audit_service, gov, store, call_count = _build()
    policy_service.create(
        "notebook-1", "allow-lookup", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"}, "lookup is safe")]
    )

    result = gov.evaluate_action({"scope_id": "notebook-1", "tool_name": "lookup", "execution_id": "exec-1"})

    assert isinstance(result, GovernanceResult)
    assert result.blocked is False
    assert result.decision.decision == ALLOW
    assert result.audit is not None
    assert result.audit.decision == ALLOW

    store.add(_plan("plan-1", "lookup"))
    step_result = gov.execute_step("plan-1", "step-1", "user:ada")
    assert step_result.status == SUCCEEDED
    assert call_count["calls"] == 1


def test_full_deny_flow():
    policy_service, audit_service, gov, store, call_count = _build(tool_name="delete")
    policy_service.create(
        "notebook-1", "deny-delete", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )

    result = gov.evaluate_action({"scope_id": "notebook-1", "tool_name": "delete", "execution_id": "exec-1"})

    assert result.blocked is True
    assert result.decision.decision == DENY
    assert result.audit.decision == DENY

    store.add(_plan("plan-1", "delete"))
    step_result = gov.execute_step("plan-1", "step-1", "user:ada")
    assert step_result.status == DENIED
    assert call_count["calls"] == 0


def test_exception_flow():
    exception_service = LLMAgentPolicyExceptionService()
    policy_service, audit_service, gov, store, call_count = _build(tool_name="delete", exception_service=exception_service)
    policy = policy_service.create(
        "notebook-1", "deny-delete", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    exception_service.create(
        "notebook-1", policy.policy_id, {"tool_name": "delete"}, "approved maintenance window", FUTURE
    )

    result = gov.evaluate_action({"scope_id": "notebook-1", "tool_name": "delete", "execution_id": "exec-1"})

    assert result.blocked is False
    assert result.decision.decision == ALLOW
    assert len(result.decision.exceptions_applied) == 1
    assert result.audit.exceptions[0]["policy_id"] == policy.policy_id

    store.add(_plan("plan-1", "delete"))
    step_result = gov.execute_step("plan-1", "step-1", "user:ada")
    assert step_result.status == SUCCEEDED
    assert call_count["calls"] == 1


def test_policy_resolution_failure():
    class ExplodingResolver:
        def resolve(self, scope_id, context=None):
            raise RuntimeError("resolver is misconfigured")

    enforcement = LLMAgentPolicyEnforcement(ExplodingResolver(), LLMAgentPolicyDecisionEngine())
    audit_service = LLMAgentPolicyAuditService()
    gov = LLMAgentPolicyGovernanceOrchestrator(enforcement=enforcement, audit_service=audit_service)

    with pytest.raises(PolicyEvaluationFailedError):
        gov.evaluate_action({"scope_id": "notebook-1", "tool_name": "lookup"})


def test_audit_integration():
    policy_service, audit_service, gov, store, call_count = _build()
    policy_service.create(
        "notebook-1", "deny-lookup", [_rule("deny-lookup", DENY, {"tool_name": "lookup"}, "blocked")]
    )

    gov.evaluate_action({"scope_id": "notebook-1", "tool_name": "lookup", "execution_id": "exec-42"})

    records = audit_service.list_for_execution("exec-42")
    assert len(records) == 1
    assert records[0].decision == DENY
    assert records[0].scope_id == "notebook-1"


def test_provenance_propagation():
    policy_service, audit_service, gov, store, call_count = _build()
    policy = policy_service.create(
        "notebook-1", "allow-lookup", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"}, "fine")]
    )

    result = gov.evaluate_action({"scope_id": "notebook-1", "tool_name": "lookup", "execution_id": "exec-1"})

    assert result.scope_id == "notebook-1"
    assert result.execution_or_action_id == "exec-1"
    assert len(result.decision.provenance) == 1
    assert result.decision.provenance[0].resolved.policy.policy_id == policy.policy_id
    assert result.audit.matched_rules[0]["policy_id"] == policy.policy_id


def test_evaluate_action_without_identifier_skips_audit_gracefully():
    policy_service, audit_service, gov, store, call_count = _build()
    policy_service.create("notebook-1", "allow-lookup", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})])

    result = gov.evaluate_action({"scope_id": "notebook-1", "tool_name": "lookup"})

    assert result.blocked is False
    assert result.audit is None


def test_scope_isolation():
    policy_service, audit_service, gov, store, call_count = _build()
    policy_service.create("notebook-1", "allow-lookup", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})])
    policy_service.create("notebook-2", "deny-lookup", [_rule("deny-lookup", DENY, {"tool_name": "lookup"})])

    result_1 = gov.evaluate_action({"scope_id": "notebook-1", "tool_name": "lookup", "execution_id": "exec-1"})
    result_2 = gov.evaluate_action({"scope_id": "notebook-2", "tool_name": "lookup", "execution_id": "exec-2"})

    assert result_1.blocked is False
    assert result_2.blocked is True
    assert audit_service.list_for_scope("notebook-1")[0].decision == ALLOW
    assert audit_service.list_for_scope("notebook-2")[0].decision == DENY


def test_execution_boundary_integration():
    policy_service, audit_service, gov, store, call_count = _build(tool_name="lookup")
    policy_service.create("notebook-1", "allow-lookup", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})])
    store.add(_plan("plan-1", "lookup"))

    result = gov.execute_step("plan-1", "step-1", "user:ada")

    assert result.status == SUCCEEDED
    assert call_count["calls"] == 1
    # the real execution was itself audited by the configured execution_service
    records = audit_service.list_for_execution(result.execution_id)
    assert len(records) == 1
    assert records[0].decision == ALLOW


def test_execute_step_without_execution_service_raises():
    enforcement = LLMAgentPolicyEnforcement(
        LLMAgentPolicyResolver(LLMAgentPolicyService()), LLMAgentPolicyDecisionEngine()
    )
    gov = LLMAgentPolicyGovernanceOrchestrator(enforcement=enforcement, audit_service=LLMAgentPolicyAuditService())

    with pytest.raises(NoExecutionBoundaryConfiguredError):
        gov.execute_step("plan-1", "step-1", "user:ada")


def test_regression_coverage_no_policy_configured():
    """Existing behavior remains unchanged when governance has no
    applicable restriction: with zero policies configured for the scope,
    the action proceeds exactly as it would have before this series
    existed."""
    policy_service, audit_service, gov, store, call_count = _build()
    store.add(_plan("plan-1", "lookup"))

    result = gov.evaluate_action({"scope_id": "notebook-1", "tool_name": "lookup", "execution_id": "exec-1"})
    assert result.blocked is False
    assert result.decision.decision == DENY  # raw default-deny, but not a block

    step_result = gov.execute_step("plan-1", "step-1", "user:ada")
    assert step_result.status == SUCCEEDED
    assert call_count["calls"] == 1
