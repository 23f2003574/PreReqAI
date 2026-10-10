from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_policy_audit import (
    InMemoryLLMAgentPolicyDecisionAuditStore,
    LLMAgentPolicyAuditedExecutionService,
    LLMAgentPolicyAuditService,
    LLMAgentPolicyDecisionAudit,
    UnknownPolicyDecisionAuditError,
)
from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine, PolicyDecision
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement
from backend.agent_policy_exceptions import LLMAgentPolicyExceptionAwareDecisionEngine, LLMAgentPolicyExceptionService
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


def _resolved_for(scope_id, rules):
    policy_service = LLMAgentPolicyService()
    created = policy_service.create(scope_id, "test-policy", rules)
    resolver = LLMAgentPolicyResolver(policy_service)
    return created, resolver.resolve(scope_id)


# --- record()/get()/list_for_* -----------------------------------------


def test_allow_audit():
    policy, resolved = _resolved_for(
        "notebook-1", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"}, "lookup is safe")]
    )
    decision = LLMAgentPolicyDecisionEngine().decide({"scope_id": "notebook-1", "tool_name": "lookup"}, resolved)
    audit_service = LLMAgentPolicyAuditService()

    record = audit_service.record("notebook-1", "exec-1", decision)

    assert isinstance(record, LLMAgentPolicyDecisionAudit)
    assert record.audit_id is not None
    assert record.decision == ALLOW
    assert record.scope_id == "notebook-1"
    assert record.execution_or_action_id == "exec-1"
    assert record.matched_rules == [
        {"policy_id": policy.policy_id, "rule_id": "allow-lookup", "effect": ALLOW, "reason": "lookup is safe"}
    ]
    assert record.exceptions == []
    assert record.created_at is not None


def test_deny_audit():
    policy, resolved = _resolved_for(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    decision = LLMAgentPolicyDecisionEngine().decide({"scope_id": "notebook-1", "tool_name": "delete"}, resolved)
    audit_service = LLMAgentPolicyAuditService()

    record = audit_service.record("notebook-1", "exec-2", decision)

    assert record.decision == DENY
    assert record.matched_rules == [
        {"policy_id": policy.policy_id, "rule_id": "deny-delete", "effect": DENY, "reason": "delete is blocked"}
    ]


def test_missing_audit():
    audit_service = LLMAgentPolicyAuditService()
    with pytest.raises(UnknownPolicyDecisionAuditError):
        audit_service.get("missing-id")


def test_invalid_record_arguments():
    policy, resolved = _resolved_for("notebook-1", [_rule("allow-lookup", ALLOW)])
    decision = LLMAgentPolicyDecisionEngine().decide({"scope_id": "notebook-1"}, resolved)
    audit_service = LLMAgentPolicyAuditService()

    with pytest.raises(ValueError):
        audit_service.record("", "exec-1", decision)
    with pytest.raises(ValueError):
        audit_service.record("notebook-1", "", decision)
    with pytest.raises(ValueError):
        audit_service.record("notebook-1", "exec-1", "not-a-decision")


def test_exception_audit():
    policy, resolved = _resolved_for(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    exception_service = LLMAgentPolicyExceptionService()
    exception_service.create(
        "notebook-1", policy.policy_id, {"tool_name": "delete"}, "approved maintenance window", FUTURE
    )
    engine = LLMAgentPolicyExceptionAwareDecisionEngine(exception_service)
    decision = engine.decide({"scope_id": "notebook-1", "tool_name": "delete"}, resolved)
    assert decision.decision == ALLOW  # sanity: the exception really applied

    audit_service = LLMAgentPolicyAuditService()
    record = audit_service.record("notebook-1", "exec-3", decision)

    assert record.decision == ALLOW
    assert len(record.exceptions) == 1
    assert record.exceptions[0]["policy_id"] == policy.policy_id
    assert record.exceptions[0]["reason"] == "approved maintenance window"


def test_provenance_traceable_by_reference():
    policy, resolved = _resolved_for(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    decision = LLMAgentPolicyDecisionEngine().decide({"scope_id": "notebook-1", "tool_name": "delete"}, resolved)
    audit_service = LLMAgentPolicyAuditService()
    record = audit_service.record("notebook-1", "exec-4", decision)

    # the audit record traces back to the real policy/rule by reference,
    # never by copying the policy's own rule set
    assert record.matched_rules[0]["policy_id"] == policy.policy_id
    assert record.matched_rules[0]["rule_id"] == "deny-delete"
    fetched = audit_service.get(record.audit_id)
    assert fetched == record


def test_scope_isolation():
    policy_1, resolved_1 = _resolved_for("notebook-1", [_rule("allow-1", ALLOW, {"tool_name": "lookup"})])
    policy_2, resolved_2 = _resolved_for("notebook-2", [_rule("allow-2", ALLOW, {"tool_name": "lookup"})])
    engine = LLMAgentPolicyDecisionEngine()
    decision_1 = engine.decide({"scope_id": "notebook-1", "tool_name": "lookup"}, resolved_1)
    decision_2 = engine.decide({"scope_id": "notebook-2", "tool_name": "lookup"}, resolved_2)

    audit_service = LLMAgentPolicyAuditService()
    audit_service.record("notebook-1", "exec-1", decision_1)
    audit_service.record("notebook-2", "exec-2", decision_2)

    scope_1_records = audit_service.list_for_scope("notebook-1")
    scope_2_records = audit_service.list_for_scope("notebook-2")

    assert [item.scope_id for item in scope_1_records] == ["notebook-1"]
    assert [item.scope_id for item in scope_2_records] == ["notebook-2"]


def test_retrieval_and_filtering():
    policy, resolved = _resolved_for("notebook-1", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})])
    engine = LLMAgentPolicyDecisionEngine()
    decision = engine.decide({"scope_id": "notebook-1", "tool_name": "lookup"}, resolved)

    audit_service = LLMAgentPolicyAuditService()
    first = audit_service.record("notebook-1", "exec-1", decision)
    second = audit_service.record("notebook-1", "exec-1", decision)  # same execution, two decisions
    third = audit_service.record("notebook-1", "exec-2", decision)

    for_exec_1 = audit_service.list_for_execution("exec-1")
    assert [item.audit_id for item in for_exec_1] == [first.audit_id, second.audit_id]

    for_scope = audit_service.list_for_scope("notebook-1")
    assert [item.audit_id for item in for_scope] == [first.audit_id, second.audit_id, third.audit_id]


def test_sensitive_data_is_redacted_and_never_stores_raw_arguments():
    policy, resolved = _resolved_for(
        "notebook-1",
        [_rule("deny-secret", DENY, {"tool_name": "delete"}, "blocked: api_key: sk-abcdefghijklmnopqrstuvwxyz")],
    )
    engine = LLMAgentPolicyDecisionEngine()
    decision = engine.decide(
        {"scope_id": "notebook-1", "tool_name": "delete", "arguments": {"password": "hunter2"}}, resolved
    )
    audit_service = LLMAgentPolicyAuditService()

    record = audit_service.record("notebook-1", "exec-1", decision)

    # the secret embedded in the rule's own reason is redacted
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in record.matched_rules[0]["reason"]
    assert record.matched_rules[0]["reason"] == "[REDACTED]"
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in record.reasons[0]

    # the raw action payload/arguments were never stored at all
    dumped = str(record.to_dict())
    assert "hunter2" not in dumped
    assert "arguments" not in dumped


# --- integration into the real execution boundary -----------------------


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


def test_enforcement_integration_records_audit_for_real_execution():
    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness("lookup", call_count)
    store.add(_plan("plan-1", "lookup"))

    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "notebook-1", "allow-policy", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"}, "generally fine")]
    )
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    audit_service = LLMAgentPolicyAuditService()

    service = LLMAgentPolicyAuditedExecutionService(
        store, validation_service, orchestrator, enforcement,
        scope_for_plan=lambda plan_id: "notebook-1", audit_service=audit_service,
    )

    result = service.execute_step("plan-1", "step-1", "user:ada")
    assert result.status == SUCCEEDED

    records = audit_service.list_for_execution(result.execution_id)
    assert len(records) == 1
    assert records[0].decision == ALLOW
    assert records[0].scope_id == "notebook-1"


def test_audit_failure_does_not_change_decision():
    class BrokenStore(InMemoryLLMAgentPolicyDecisionAuditStore):
        def save(self, audit):
            raise RuntimeError("audit store is unavailable")

    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness("lookup", call_count)
    store.add(_plan("plan-1", "lookup"))

    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "notebook-1", "allow-policy", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})]
    )
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    audit_service = LLMAgentPolicyAuditService(store=BrokenStore())

    service = LLMAgentPolicyAuditedExecutionService(
        store, validation_service, orchestrator, enforcement,
        scope_for_plan=lambda plan_id: "notebook-1", audit_service=audit_service,
    )

    # the action still succeeds and executes for real, despite the
    # audit store being completely broken
    result = service.execute_step("plan-1", "step-1", "user:ada")
    assert result.status == SUCCEEDED
    assert call_count["calls"] == 1


def test_audit_failure_does_not_change_denied_decision():
    class BrokenStore(InMemoryLLMAgentPolicyDecisionAuditStore):
        def save(self, audit):
            raise RuntimeError("audit store is unavailable")

    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness("delete", call_count)
    store.add(_plan("plan-1", "delete"))

    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "notebook-1", "deny-policy", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "blocked")]
    )
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    audit_service = LLMAgentPolicyAuditService(store=BrokenStore())

    service = LLMAgentPolicyAuditedExecutionService(
        store, validation_service, orchestrator, enforcement,
        scope_for_plan=lambda plan_id: "notebook-1", audit_service=audit_service,
    )

    result = service.execute_step("plan-1", "step-1", "user:ada")
    assert result.status == DENIED
    assert call_count["calls"] == 0
