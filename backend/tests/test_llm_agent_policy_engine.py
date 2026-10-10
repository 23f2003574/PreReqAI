import pytest

from backend.agent_policy_engine import (
    ACTIVE,
    ALLOW,
    ARCHIVED,
    DENY,
    ArchivedPolicyError,
    DuplicateRuleIdError,
    InvalidAgentPolicyError,
    InvalidPolicyEvaluationError,
    InvalidPolicyRuleError,
    LLMAgentPolicy,
    LLMAgentPolicyEvaluator,
    LLMAgentPolicyRule,
    LLMAgentPolicyService,
    UnknownAgentPolicyError,
)


def _rule(rule_id, effect, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def _services():
    return LLMAgentPolicyService(), LLMAgentPolicyEvaluator()


def test_create_and_get():
    service, _ = _services()

    created = service.create(
        "notebook-1", "tool-access", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})],
    )

    assert isinstance(created, LLMAgentPolicy)
    assert created.policy_id is not None
    assert created.status == ACTIVE
    assert created.scope_id == "notebook-1"
    assert created.created_at is not None
    assert created.updated_at is not None

    fetched = service.get(created.policy_id)
    assert fetched.name == "tool-access"
    assert [rule.rule_id for rule in fetched.rules] == ["allow-lookup"]


def test_missing_policy():
    service, _ = _services()

    with pytest.raises(UnknownAgentPolicyError):
        service.get("missing-id")

    with pytest.raises(UnknownAgentPolicyError):
        service.update("missing-id", name="new name")

    with pytest.raises(UnknownAgentPolicyError):
        service.archive("missing-id")


def test_crud_lifecycle():
    service, _ = _services()

    created = service.create("notebook-1", "tool-access", [_rule("allow-lookup", ALLOW)])

    updated = service.update(
        created.policy_id, name="tool-access-v2", rules=[_rule("deny-delete", DENY, {"tool_name": "delete"})]
    )
    assert updated.name == "tool-access-v2"
    assert [rule.rule_id for rule in updated.rules] == ["deny-delete"]
    assert updated.status == ACTIVE

    archived = service.archive(created.policy_id)
    assert archived.status == ARCHIVED

    still_there = service.get(created.policy_id)
    assert still_there.status == ARCHIVED


def test_scope_isolation():
    service, _ = _services()

    service.create("notebook-1", "policy-1", [_rule("r1", ALLOW)])
    service.create("notebook-2", "policy-2", [_rule("r2", ALLOW)])

    notebook_1 = service.list("notebook-1")
    notebook_2 = service.list("notebook-2")

    assert [item.name for item in notebook_1] == ["policy-1"]
    assert [item.name for item in notebook_2] == ["policy-2"]


def test_invalid_policy():
    service, _ = _services()

    with pytest.raises(InvalidAgentPolicyError):
        service.create("", "name", [_rule("r1", ALLOW)])

    with pytest.raises(InvalidAgentPolicyError):
        service.create("notebook-1", "", [_rule("r1", ALLOW)])

    with pytest.raises(InvalidAgentPolicyError):
        service.create("notebook-1", "name", "not-a-list")

    with pytest.raises(InvalidPolicyRuleError):
        service.create("notebook-1", "name", [{"rule_id": "r1", "effect": "MAYBE"}])

    with pytest.raises(DuplicateRuleIdError):
        service.create(
            "notebook-1", "name",
            [_rule("dup", ALLOW, {"tool_name": "a"}), _rule("dup", DENY, {"tool_name": "b"})],
        )


def test_archived_record_cannot_be_updated():
    service, _ = _services()
    created = service.create("notebook-1", "tool-access", [_rule("r1", ALLOW)])

    archived_once = service.archive(created.policy_id)
    assert archived_once.status == ARCHIVED

    # archiving an already-archived policy is a no-op, not an error
    archived_twice = service.archive(created.policy_id)
    assert archived_twice.status == ARCHIVED

    with pytest.raises(ArchivedPolicyError):
        service.update(created.policy_id, name="renamed")

    # archived policies remain listable, never deleted
    still_listed = service.list("notebook-1", status=ARCHIVED)
    assert [item.policy_id for item in still_listed] == [created.policy_id]


def test_allow_and_default_deny_evaluation():
    service, evaluator = _services()
    policy = service.create(
        "notebook-1", "tool-access", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})],
    )

    allowed = evaluator.evaluate(policy, {"tool_name": "lookup"})
    assert allowed.allowed is True
    assert allowed.effect == ALLOW
    assert allowed.rule_id == "allow-lookup"
    assert allowed.policy_id == policy.policy_id

    denied_by_default = evaluator.evaluate(policy, {"tool_name": "delete"})
    assert denied_by_default.allowed is False
    assert denied_by_default.effect == DENY
    assert denied_by_default.rule_id is None
    assert "denied by default" in denied_by_default.reason


def test_conflicting_rules_explicit_deny_wins():
    service, evaluator = _services()

    # deny listed after allow -- deny must still win regardless of order
    policy = service.create(
        "notebook-1", "conflicting",
        [
            _rule("allow-all-lookup", ALLOW, {"tool_name": "lookup"}),
            _rule("deny-admin-lookup", DENY, {"tool_name": "lookup", "subject": "admin"}),
        ],
    )

    decision = evaluator.evaluate(policy, {"tool_name": "lookup", "subject": "admin"})
    assert decision.allowed is False
    assert decision.effect == DENY
    assert decision.rule_id == "deny-admin-lookup"

    # the same policy still allows a non-conflicting match
    other = evaluator.evaluate(policy, {"tool_name": "lookup", "subject": "guest"})
    assert other.allowed is True
    assert other.rule_id == "allow-all-lookup"

    # deterministic: re-evaluating the identical action reaches the same decision
    repeat = evaluator.evaluate(policy, {"tool_name": "lookup", "subject": "admin"})
    assert repeat == decision


def test_archived_policy_denies_unconditionally():
    service, evaluator = _services()
    policy = service.create(
        "notebook-1", "tool-access", [_rule("allow-lookup", ALLOW, {"tool_name": "lookup"})],
    )
    archived = service.archive(policy.policy_id)

    decision = evaluator.evaluate(archived, {"tool_name": "lookup"})
    assert decision.allowed is False
    assert decision.effect == DENY
    assert decision.rule_id is None
    assert "archived" in decision.reason


def test_evaluation_provenance():
    service, evaluator = _services()
    policy = service.create(
        "notebook-1", "tool-access",
        [
            _rule("deny-delete", DENY, {"tool_name": "delete"}, reason="delete is never permitted"),
            _rule("allow-lookup", ALLOW, {"tool_name": "lookup"}, reason="lookup is safe"),
        ],
    )

    denied = evaluator.evaluate(policy, {"tool_name": "delete"})
    assert denied.policy_id == policy.policy_id
    assert denied.rule_id == "deny-delete"
    assert denied.reason == "delete is never permitted"

    allowed = evaluator.evaluate(policy, {"tool_name": "lookup"})
    assert allowed.policy_id == policy.policy_id
    assert allowed.rule_id == "allow-lookup"
    assert allowed.reason == "lookup is safe"


def test_evaluate_rejects_invalid_arguments():
    _, evaluator = _services()

    with pytest.raises(InvalidPolicyEvaluationError):
        evaluator.evaluate("not-a-policy", {"tool_name": "lookup"})

    policy = LLMAgentPolicy(scope_id="notebook-1", name="p", rules=[_rule("r1", ALLOW)])
    with pytest.raises(InvalidPolicyEvaluationError):
        evaluator.evaluate(policy, "not-a-dict")
