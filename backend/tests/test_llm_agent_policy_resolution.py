import pytest

from backend.agent_policy_engine import ACTIVE, ALLOW, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_resolution import (
    LLMAgentPolicyResolver,
    PolicyPrecedenceError,
    ResolvedPolicy,
    UnknownExecutionScopeError,
)


def _rule(rule_id, effect=ALLOW, match=None):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {})


def _services():
    policy_service = LLMAgentPolicyService()
    resolver = LLMAgentPolicyResolver(policy_service)
    return policy_service, resolver


def test_single_policy():
    policy_service, resolver = _services()
    created = policy_service.create("notebook-1", "only-policy", [_rule("r1")])

    resolved = resolver.resolve("notebook-1")

    assert len(resolved) == 1
    assert isinstance(resolved[0], ResolvedPolicy)
    assert resolved[0].policy.policy_id == created.policy_id
    assert resolved[0].precedence == 0
    assert resolved[0].source == "scope:notebook-1"


def test_multiple_applicable_policies_default_creation_order():
    policy_service, resolver = _services()
    first = policy_service.create("notebook-1", "first", [_rule("r1")])
    second = policy_service.create("notebook-1", "second", [_rule("r2")])

    resolved = resolver.resolve("notebook-1")

    assert [item.policy.policy_id for item in resolved] == [first.policy_id, second.policy_id]
    assert [item.precedence for item in resolved] == [0, 1]


def test_explicit_precedence_overrides_creation_order():
    policy_service, resolver = _services()
    first = policy_service.create("notebook-1", "first", [_rule("r1")])
    second = policy_service.create("notebook-1", "second", [_rule("r2")])

    # second was created after first, but is explicitly declared to outrank it
    resolver.set_precedence(second.policy_id, higher_than=first.policy_id)

    resolved = resolver.resolve("notebook-1")

    assert [item.policy.policy_id for item in resolved] == [second.policy_id, first.policy_id]
    assert [item.precedence for item in resolved] == [0, 1]


def test_conflicting_precedence_rules_rejected_deterministically():
    policy_service, resolver = _services()
    first = policy_service.create("notebook-1", "first", [_rule("r1")])
    second = policy_service.create("notebook-1", "second", [_rule("r2")])

    resolver.set_precedence(second.policy_id, higher_than=first.policy_id)

    with pytest.raises(PolicyPrecedenceError):
        resolver.set_precedence(first.policy_id, higher_than=second.policy_id)

    with pytest.raises(PolicyPrecedenceError):
        resolver.set_precedence(first.policy_id, higher_than=first.policy_id)


def test_scope_isolation():
    policy_service, resolver = _services()
    policy_service.create("notebook-1", "policy-1", [_rule("r1")])
    policy_service.create("notebook-2", "policy-2", [_rule("r2")])

    resolved_1 = resolver.resolve("notebook-1")
    resolved_2 = resolver.resolve("notebook-2")

    assert [item.policy.name for item in resolved_1] == ["policy-1"]
    assert [item.policy.name for item in resolved_2] == ["policy-2"]
    assert all(item.source == "scope:notebook-1" for item in resolved_1)
    assert all(item.source == "scope:notebook-2" for item in resolved_2)


def test_no_applicable_policy():
    _, resolver = _services()
    assert resolver.resolve("empty-scope") == []


def test_archived_policy_excluded_from_resolution():
    policy_service, resolver = _services()
    created = policy_service.create("notebook-1", "retiring", [_rule("r1")])
    policy_service.archive(created.policy_id)

    assert resolver.resolve("notebook-1") == []


def test_provenance():
    policy_service, resolver = _services()
    created = policy_service.create("notebook-1", "only-policy", [_rule("r1")])

    resolved = resolver.resolve("notebook-1")

    assert resolved[0].policy.policy_id == created.policy_id
    assert resolved[0].policy.status == ACTIVE
    assert resolved[0].source == "scope:notebook-1"
    assert resolved[0].precedence == 0


def test_deterministic_resolution():
    policy_service, resolver = _services()
    policy_service.create("notebook-1", "first", [_rule("r1")])
    policy_service.create("notebook-1", "second", [_rule("r2")])

    first_call = resolver.resolve("notebook-1")
    second_call = resolver.resolve("notebook-1")

    assert first_call == second_call


def test_resolve_for_execution_uses_scope_mapping():
    policy_service = LLMAgentPolicyService()
    created = policy_service.create("notebook-1", "only-policy", [_rule("r1")])
    resolver = LLMAgentPolicyResolver(policy_service, scope_for_execution={"exec-1": "notebook-1"}.get)

    resolved = resolver.resolve_for_execution("exec-1")

    assert [item.policy.policy_id for item in resolved] == [created.policy_id]
    assert resolved[0].source == "scope:notebook-1"


def test_resolve_for_execution_without_mapping_raises():
    _, resolver = _services()

    with pytest.raises(UnknownExecutionScopeError):
        resolver.resolve_for_execution("exec-1")


def test_resolve_for_execution_unknown_execution_raises():
    policy_service = LLMAgentPolicyService()
    resolver = LLMAgentPolicyResolver(policy_service, scope_for_execution={}.get)

    with pytest.raises(UnknownExecutionScopeError):
        resolver.resolve_for_execution("missing-exec")
