import pytest

from backend.agent_policy_engine import ALLOW, DENY, InMemoryLLMAgentPolicyStore, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_history import LLMAgentPolicyHistoryService, LLMAgentPolicyHistoryTrackedService
from backend.agent_policy_rollback import LLMAgentPolicyRollbackError, LLMAgentPolicyRollbackService
from backend.agent_policy_versioning import LLMAgentPolicyVersionService


def _rule(rule_id, effect=ALLOW, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _services():
    store = InMemoryLLMAgentPolicyStore()
    history_service = LLMAgentPolicyHistoryService()
    tracked_policy_service = LLMAgentPolicyHistoryTrackedService(store=store, history_service=history_service)
    raw_policy_service = LLMAgentPolicyService(store=store)
    version_service = LLMAgentPolicyVersionService(raw_policy_service, history_service)
    rollback_service = LLMAgentPolicyRollbackService(version_service)
    return tracked_policy_service, history_service, version_service, rollback_service


def test_rollback_to_valid_version():
    policy_service, _, version_service, rollback_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY)])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY), _rule("r3", DENY)])

    result = rollback_service.rollback(created.policy_id, 1, reason="v3 caused a regression")

    assert [rule["rule_id"] for rule in result.rules] == ["r1"]
    live = policy_service.get(created.policy_id)
    assert [rule.rule_id for rule in live.rules] == ["r1"]


def test_invalid_target_version_rejected():
    policy_service, _, _, rollback_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])

    with pytest.raises(LLMAgentPolicyRollbackError):
        rollback_service.rollback(created.policy_id, 99, reason="does not exist")

    with pytest.raises(LLMAgentPolicyRollbackError):
        rollback_service.rollback("unknown-policy", 1, reason="unknown policy")


def test_new_version_created():
    policy_service, _, version_service, rollback_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY)])

    result = rollback_service.rollback(created.policy_id, 1, reason="revert to v1")

    versions = version_service.list_versions(created.policy_id)
    assert [v.version for v in versions] == [1, 2, 3]
    assert versions[-1] == result
    assert [rule["rule_id"] for rule in versions[-1].rules] == ["r1"]


def test_old_versions_unchanged():
    policy_service, _, version_service, rollback_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY)])

    v1_before = version_service.get_version(created.policy_id, 1)
    v2_before = version_service.get_version(created.policy_id, 2)

    rollback_service.rollback(created.policy_id, 1, reason="revert")

    v1_after = version_service.get_version(created.policy_id, 1)
    v2_after = version_service.get_version(created.policy_id, 2)
    assert v1_after == v1_before
    assert v2_after == v2_before


def test_provenance_and_reason():
    policy_service, history_service, version_service, rollback_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY)])

    result = rollback_service.rollback(created.policy_id, 1, reason="v2 broke lookups", actor="user:ada")

    change = history_service.get(result.version_id)
    assert change.actor == "user:ada"
    assert "v2 broke lookups" in change.reason
    assert "rollback to version 1" in change.reason
    assert change.policy_id == created.policy_id


def test_validation_failure_on_archived_policy():
    policy_service, _, version_service, rollback_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY)])
    policy_service.archive(created.policy_id)

    with pytest.raises(LLMAgentPolicyRollbackError):
        rollback_service.rollback(created.policy_id, 1, reason="try to revert an archived policy")


def test_scope_isolation():
    policy_service, history_service, version_service, rollback_service = _services()
    policy_1 = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    policy_2 = policy_service.create("notebook-2", "policy-b", [_rule("r1")])
    version_service.create_version(policy_1.policy_id, [_rule("r1"), _rule("r2", DENY)])
    version_service.create_version(policy_2.policy_id, [_rule("r1"), _rule("r2", DENY)])

    rollback_service.rollback(policy_1.policy_id, 1, reason="revert notebook-1 only")

    live_1 = policy_service.get(policy_1.policy_id)
    live_2 = policy_service.get(policy_2.policy_id)
    assert [rule.rule_id for rule in live_1.rules] == ["r1"]
    assert [rule.rule_id for rule in live_2.rules] == ["r1", "r2"]  # untouched

    scope_1_history = history_service.list_for_scope("notebook-1")
    scope_2_history = history_service.list_for_scope("notebook-2")
    assert all(item.policy_id == policy_1.policy_id for item in scope_1_history)
    assert all(item.policy_id == policy_2.policy_id for item in scope_2_history)


def test_rollback_idempotency():
    policy_service, _, version_service, rollback_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY)])

    first = rollback_service.rollback(created.policy_id, 1, reason="revert")
    second = rollback_service.rollback(created.policy_id, 1, reason="revert again, already there")

    # no duplicate version was created the second time
    versions = version_service.list_versions(created.policy_id)
    assert [v.version for v in versions] == [1, 2, 3]
    assert first == second
    assert first.version_id == second.version_id
