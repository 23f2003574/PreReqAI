from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_plan_validation import LLMAgentPlanValidationService
from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_enforcement import LLMAgentPolicyEnforcedExecutionService, LLMAgentPolicyEnforcement
from backend.agent_policy_exceptions import (
    ACTIVE,
    REVOKED,
    InvalidPolicyExceptionError,
    LLMAgentPolicyException,
    LLMAgentPolicyExceptionAwareDecisionEngine,
    LLMAgentPolicyExceptionService,
    UnknownPolicyExceptionError,
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
PAST = datetime.now(timezone.utc) - timedelta(days=1)


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _services():
    return LLMAgentPolicyExceptionService()


# --- CRUD / lifecycle -------------------------------------------------


def test_valid_exception():
    service = _services()
    created = service.create(
        "notebook-1", "policy-1", {"tool_name": "delete"}, "temporary maintenance access", FUTURE
    )

    assert isinstance(created, LLMAgentPolicyException)
    assert created.exception_id is not None
    assert created.status == ACTIVE
    assert created.created_at is not None

    fetched = service.get(created.exception_id)
    assert fetched.scope_id == "notebook-1"
    assert fetched.policy_id == "policy-1"
    assert fetched.match == {"tool_name": "delete"}
    assert fetched.reason == "temporary maintenance access"


def test_missing_exception():
    service = _services()
    with pytest.raises(UnknownPolicyExceptionError):
        service.get("missing-id")
    with pytest.raises(UnknownPolicyExceptionError):
        service.revoke("missing-id")
    with pytest.raises(UnknownPolicyExceptionError):
        service.is_active("missing-id")


def test_invalid_exception_rejected():
    service = _services()

    with pytest.raises(InvalidPolicyExceptionError):
        service.create("", "policy-1", {"tool_name": "delete"}, "reason", FUTURE)

    with pytest.raises(InvalidPolicyExceptionError):
        service.create("notebook-1", "", {"tool_name": "delete"}, "reason", FUTURE)

    with pytest.raises(InvalidPolicyExceptionError):
        service.create("notebook-1", "policy-1", {}, "reason", FUTURE)  # no blanket exceptions

    with pytest.raises(InvalidPolicyExceptionError):
        service.create("notebook-1", "policy-1", {"tool_name": "delete"}, "", FUTURE)

    with pytest.raises(InvalidPolicyExceptionError):
        service.create("notebook-1", "policy-1", {"tool_name": "delete"}, "reason", None)


def test_active_override():
    service = _services()
    created = service.create("notebook-1", "policy-1", {"tool_name": "delete"}, "reason", FUTURE)

    assert service.is_active(created.exception_id) is True

    applicable = service.applicable("notebook-1", "policy-1", {"tool_name": "delete"})
    assert [item.exception_id for item in applicable] == [created.exception_id]


def test_expired_exception_cannot_override():
    service = _services()
    created = service.create("notebook-1", "policy-1", {"tool_name": "delete"}, "reason", PAST)

    assert service.is_active(created.exception_id) is False
    assert service.applicable("notebook-1", "policy-1", {"tool_name": "delete"}) == []


def test_revoked_exception_cannot_override():
    service = _services()
    created = service.create("notebook-1", "policy-1", {"tool_name": "delete"}, "reason", FUTURE)

    revoked_once = service.revoke(created.exception_id)
    assert revoked_once.status == REVOKED
    assert service.is_active(created.exception_id) is False
    assert service.applicable("notebook-1", "policy-1", {"tool_name": "delete"}) == []

    # revoking twice is a no-op, not an error, and the reason is retained
    revoked_twice = service.revoke(created.exception_id)
    assert revoked_twice.status == REVOKED
    assert revoked_twice.reason == "reason"


def test_scope_isolation():
    service = _services()
    service.create("notebook-1", "policy-1", {"tool_name": "delete"}, "reason", FUTURE)
    service.create("notebook-2", "policy-1", {"tool_name": "delete"}, "reason", FUTURE)

    notebook_1 = service.list("notebook-1")
    notebook_2 = service.list("notebook-2")
    assert len(notebook_1) == 1 and notebook_1[0].scope_id == "notebook-1"
    assert len(notebook_2) == 1 and notebook_2[0].scope_id == "notebook-2"

    # an exception granted in notebook-2 never applies within notebook-1,
    # even for the exact same policy_id and matching action
    applicable_in_1 = service.applicable("notebook-1", "policy-1", {"tool_name": "delete"})
    assert [item.exception_id for item in applicable_in_1] == [notebook_1[0].exception_id]

    applicable_in_2 = service.applicable("notebook-2", "policy-1", {"tool_name": "delete"})
    assert [item.exception_id for item in applicable_in_2] == [notebook_2[0].exception_id]


def test_narrow_vs_broad_match_preference():
    service = _services()
    broad = service.create("notebook-1", "policy-1", {"tool_name": "delete"}, "broad relief", FUTURE)
    narrow = service.create(
        "notebook-1", "policy-1", {"tool_name": "delete", "subject": "user:ada"}, "narrow relief", FUTURE
    )

    action = {"tool_name": "delete", "subject": "user:ada"}
    applicable = service.applicable("notebook-1", "policy-1", action)

    # both apply, but the narrower (more specific) exception is preferred
    assert [item.exception_id for item in applicable] == [narrow.exception_id, broad.exception_id]

    # the broad exception still applies on its own to a less specific action
    broad_only = service.applicable("notebook-1", "policy-1", {"tool_name": "delete", "subject": "user:bob"})
    assert [item.exception_id for item in broad_only] == [broad.exception_id]


def test_provenance():
    service = _services()
    created = service.create(
        "notebook-1", "policy-1", {"tool_name": "delete"}, "approved by compliance for maintenance window", FUTURE
    )

    fetched = service.get(created.exception_id)
    assert fetched.reason == "approved by compliance for maintenance window"
    assert fetched.policy_id == "policy-1"
    assert fetched.scope_id == "notebook-1"

    revoked = service.revoke(created.exception_id)
    # the reason and original grant details survive revocation
    assert revoked.reason == "approved by compliance for maintenance window"
    assert revoked.policy_id == "policy-1"


# --- integration into decision evaluation -----------------------------


def _resolved_for(scope_id, rules):
    policy_service = LLMAgentPolicyService()
    created = policy_service.create(scope_id, "test-policy", rules)
    resolver = LLMAgentPolicyResolver(policy_service)
    return created, resolver.resolve(scope_id)


def test_decision_engine_integration_allow_with_active_exception():
    policy, resolved = _resolved_for(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    exception_service = LLMAgentPolicyExceptionService()
    exception_service.create(
        "notebook-1", policy.policy_id, {"tool_name": "delete"}, "approved maintenance window", FUTURE
    )

    engine = LLMAgentPolicyExceptionAwareDecisionEngine(exception_service, LLMAgentPolicyDecisionEngine())
    decision = engine.decide({"scope_id": "notebook-1", "tool_name": "delete"}, resolved)

    assert decision.decision == ALLOW
    assert len(decision.exceptions_applied) == 1
    assert decision.exceptions_applied[0].policy_id == policy.policy_id
    assert any("approved maintenance window" in reason for reason in decision.reasons)


def test_decision_engine_integration_deny_without_matching_exception():
    policy, resolved = _resolved_for(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    exception_service = LLMAgentPolicyExceptionService()
    # an exception exists, but for a different action -- must not apply
    exception_service.create(
        "notebook-1", policy.policy_id, {"tool_name": "archive"}, "unrelated relief", FUTURE
    )

    engine = LLMAgentPolicyExceptionAwareDecisionEngine(exception_service, LLMAgentPolicyDecisionEngine())
    decision = engine.decide({"scope_id": "notebook-1", "tool_name": "delete"}, resolved)

    assert decision.decision == DENY
    assert decision.exceptions_applied == []


def test_decision_engine_integration_expired_and_revoked_exceptions_do_not_apply():
    policy, resolved = _resolved_for(
        "notebook-1", [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")]
    )
    exception_service = LLMAgentPolicyExceptionService()
    expired = exception_service.create(
        "notebook-1", policy.policy_id, {"tool_name": "delete"}, "expired relief", PAST
    )
    revocable = exception_service.create(
        "notebook-1", policy.policy_id, {"tool_name": "delete"}, "revoked relief", FUTURE
    )
    exception_service.revoke(revocable.exception_id)

    engine = LLMAgentPolicyExceptionAwareDecisionEngine(exception_service, LLMAgentPolicyDecisionEngine())
    decision = engine.decide({"scope_id": "notebook-1", "tool_name": "delete"}, resolved)

    assert decision.decision == DENY
    assert decision.exceptions_applied == []
    assert expired.status == ACTIVE  # expiry is time-based, not a status flip


def test_decision_engine_unchanged_when_no_denial_exists():
    policy, resolved = _resolved_for(
        "notebook-1", [_rule("allow-delete", ALLOW, {"tool_name": "delete"})]
    )
    exception_service = LLMAgentPolicyExceptionService()

    engine = LLMAgentPolicyExceptionAwareDecisionEngine(exception_service, LLMAgentPolicyDecisionEngine())
    decision = engine.decide({"scope_id": "notebook-1", "tool_name": "delete"}, resolved)

    assert decision.decision == ALLOW
    assert decision.exceptions_applied == []


# --- full enforcement-boundary integration -----------------------------


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


def _harness(tool_name="delete", call_count=None):
    store = MultiPlanStore()
    registry = LLMToolRegistryService()
    registry.register(tool_name, f"Tool {tool_name}", SCHEMA)

    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    permissions.register(
        LLMToolPermissionPolicy(policy_id="allow-1", tool_name=tool_name, subject=ANY_SUBJECT, allowed=True)
    )

    def handler(topic):
        if call_count is not None:
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


def test_enforcement_integration_exception_unblocks_real_execution():
    call_count = {"calls": 0}
    store, validation_service, orchestrator = _harness(call_count=call_count)
    store.add(_plan("plan-1", "delete"))

    policy_service = LLMAgentPolicyService()
    policy = policy_service.create(
        "notebook-1", "deny-delete-policy",
        [_rule("deny-delete", DENY, {"tool_name": "delete"}, "delete is blocked")],
    )
    resolver = LLMAgentPolicyResolver(policy_service)
    exception_service = LLMAgentPolicyExceptionService()

    exception_aware_engine = LLMAgentPolicyExceptionAwareDecisionEngine(exception_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, exception_aware_engine)
    service = LLMAgentPolicyEnforcedExecutionService(
        store, validation_service, orchestrator, enforcement, scope_for_plan=lambda plan_id: "notebook-1"
    )

    # without an exception, the deny policy blocks the action
    blocked = service.execute_step("plan-1", "step-1", "user:ada")
    assert blocked.status == DENIED
    assert call_count["calls"] == 0

    # grant a narrow, active exception against this specific policy
    exception_service.create(
        "notebook-1", policy.policy_id, {"tool_name": "delete"}, "approved maintenance window", FUTURE
    )

    allowed = service.execute_step("plan-1", "step-1", "user:ada")
    assert allowed.status == SUCCEEDED
    assert call_count["calls"] == 1
