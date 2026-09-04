import dataclasses

import pytest

from backend.agent_policy_engine import ALLOW, DENY, InMemoryLLMAgentPolicyStore, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_history import LLMAgentPolicyHistoryService, LLMAgentPolicyHistoryTrackedService
from backend.agent_policy_versioning import LLMAgentPolicyVersion, LLMAgentPolicyVersionService, UnknownPolicyVersionError


def _rule(rule_id, effect=ALLOW, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _services():
    """A tracked service (Commit #10) for create(), sharing its store
    with a bare, untracked LLMAgentPolicyService (Commit #1) for
    LLMAgentPolicyVersionService -- so create_version()'s own update()
    call is never also auto-recorded a second time by the tracked
    wrapper, which would double-record every rule change."""
    store = InMemoryLLMAgentPolicyStore()
    history_service = LLMAgentPolicyHistoryService()
    tracked_policy_service = LLMAgentPolicyHistoryTrackedService(store=store, history_service=history_service)
    raw_policy_service = LLMAgentPolicyService(store=store)
    version_service = LLMAgentPolicyVersionService(raw_policy_service, history_service)
    return tracked_policy_service, history_service, version_service


def test_version_creation():
    policy_service, _, version_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])

    versions = version_service.list_versions(created.policy_id)

    assert len(versions) == 1
    assert isinstance(versions[0], LLMAgentPolicyVersion)
    assert versions[0].version == 1
    assert versions[0].rules == [rule.to_dict() for rule in created.rules]
    assert versions[0].policy_id == created.policy_id


def test_immutable_versions():
    policy_service, _, version_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    version = version_service.get_version(created.policy_id, 1)

    with pytest.raises(dataclasses.FrozenInstanceError):
        version.version = 99


def test_version_ordering():
    policy_service, _, version_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY)])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY), _rule("r3", DENY)])

    versions = version_service.list_versions(created.policy_id)

    assert [v.version for v in versions] == [1, 2, 3]
    timestamps = [v.created_at for v in versions]
    assert timestamps == sorted(timestamps)


def test_historical_retrieval():
    policy_service, _, version_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY)])

    v1 = version_service.get_version(created.policy_id, 1)
    v2 = version_service.get_version(created.policy_id, 2)

    assert [rule["rule_id"] for rule in v1.rules] == ["r1"]
    assert [rule["rule_id"] for rule in v2.rules] == ["r1", "r2"]

    # the policy's current live state has moved on, but v1 stays exactly
    # as it was
    current = policy_service.get(created.policy_id)
    assert [rule.rule_id for rule in current.rules] == ["r1", "r2"]
    assert [rule["rule_id"] for rule in v1.rules] == ["r1"]

    with pytest.raises(UnknownPolicyVersionError):
        version_service.get_version(created.policy_id, 99)


def test_version_diff():
    policy_service, _, version_service = _services()
    created = policy_service.create(
        "notebook-1", "policy-a", [_rule("r1", ALLOW, reason="original reason")]
    )
    version_service.create_version(
        created.policy_id,
        [_rule("r1", ALLOW, reason="updated reason"), _rule("r2", DENY, {"tool_name": "delete"})],
    )

    diff = version_service.diff(created.policy_id, 1, 2)

    assert diff["policy_id"] == created.policy_id
    assert diff["version_a"] == 1
    assert diff["version_b"] == 2
    assert [rule["rule_id"] for rule in diff["added"]] == ["r2"]
    assert diff["removed"] == []
    assert len(diff["changed"]) == 1
    assert diff["changed"][0]["rule_id"] == "r1"
    assert diff["changed"][0]["before"]["reason"] == "original reason"
    assert diff["changed"][0]["after"]["reason"] == "updated reason"


def test_policy_update_integration():
    policy_service, history_service, version_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])

    returned = version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY)], created_by="user:ada")

    # the real Commit #1 policy was actually updated
    live_policy = policy_service.get(created.policy_id)
    assert [rule.rule_id for rule in live_policy.rules] == ["r1", "r2"]

    # and a genuine Commit #10 change was recorded for it
    history = history_service.list(created.policy_id)
    assert len(history) == 2
    assert history[-1].actor == "user:ada"

    assert returned.version == 2
    assert returned.created_by == "user:ada"


def test_no_op_update_creates_no_new_version():
    policy_service, history_service, version_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])

    result = version_service.create_version(created.policy_id, [_rule("r1")])  # identical rules

    versions = version_service.list_versions(created.policy_id)
    assert len(versions) == 1
    assert result.version == 1


def test_provenance():
    policy_service, history_service, version_service = _services()
    created = policy_service.create("notebook-1", "policy-a", [_rule("r1")])
    version_service.create_version(created.policy_id, [_rule("r1"), _rule("r2", DENY)], created_by="user:ada")

    version = version_service.get_version(created.policy_id, 2)

    # version_id traces straight back to the real Commit #10 change record
    change = history_service.get(version.version_id)
    assert change.policy_id == created.policy_id
    assert change.actor == "user:ada"
    assert change.after["rules"] == version.rules
    assert version.created_at == change.created_at
