import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_engine import ALLOW, ARCHIVED, LLMAgentPolicyRule
from backend.agent_policy_exceptions import ACTIVE as EXCEPTION_ACTIVE
from backend.agent_policy_history import (
    ARCHIVED as CHANGE_ARCHIVED,
    CREATED,
    EXCEPTION_CREATED,
    EXCEPTION_REVOKED,
    UPDATED,
    InvalidPolicyChangeError,
    LLMAgentPolicyChange,
    LLMAgentPolicyExceptionHistoryTrackedService,
    LLMAgentPolicyHistoryService,
    LLMAgentPolicyHistoryTrackedService,
    UnknownPolicyChangeError,
)

FUTURE = datetime.now(timezone.utc) + timedelta(days=1)


def _rule(rule_id, effect=ALLOW, match=None, reason=""):
    return LLMAgentPolicyRule(rule_id=rule_id, effect=effect, match=match or {}, reason=reason)


def test_create_history():
    history_service = LLMAgentPolicyHistoryService()
    service = LLMAgentPolicyHistoryTrackedService(history_service=history_service, actor="user:ada")
    created = service.create("notebook-1", "policy-a", [_rule("r1")])

    history = history_service.list(created.policy_id)
    assert len(history) == 1
    assert history[0].change_type == CREATED
    assert history[0].before is None
    assert history[0].after["name"] == "policy-a"
    assert history[0].scope_id == "notebook-1"
    assert history[0].actor == "user:ada"


def test_update_history():
    history_service = LLMAgentPolicyHistoryService()
    service = LLMAgentPolicyHistoryTrackedService(history_service=history_service)
    created = service.create("notebook-1", "policy-a", [_rule("r1")])
    service.update(created.policy_id, name="policy-a-renamed")

    history = history_service.list(created.policy_id)
    assert [item.change_type for item in history] == [CREATED, UPDATED]
    assert history[1].before["name"] == "policy-a"
    assert history[1].after["name"] == "policy-a-renamed"


def test_no_op_update_records_nothing_new():
    history_service = LLMAgentPolicyHistoryService()
    service = LLMAgentPolicyHistoryTrackedService(history_service=history_service)
    created = service.create("notebook-1", "policy-a", [_rule("r1")])
    service.update(created.policy_id, name="policy-a")  # identical name -- no meaningful change

    history = history_service.list(created.policy_id)
    assert [item.change_type for item in history] == [CREATED]


def test_archive_history():
    history_service = LLMAgentPolicyHistoryService()
    service = LLMAgentPolicyHistoryTrackedService(history_service=history_service)
    created = service.create("notebook-1", "policy-a", [_rule("r1")])
    service.archive(created.policy_id)

    history = history_service.list(created.policy_id)
    assert [item.change_type for item in history] == [CREATED, CHANGE_ARCHIVED]
    assert history[1].before["status"] == "active"
    assert history[1].after["status"] == "archived"


def test_idempotent_archive_records_nothing_new():
    history_service = LLMAgentPolicyHistoryService()
    service = LLMAgentPolicyHistoryTrackedService(history_service=history_service)
    created = service.create("notebook-1", "policy-a", [_rule("r1")])
    service.archive(created.policy_id)
    service.archive(created.policy_id)  # already archived -- a true no-op

    history = history_service.list(created.policy_id)
    assert [item.change_type for item in history] == [CREATED, CHANGE_ARCHIVED]


def test_exception_changes():
    history_service = LLMAgentPolicyHistoryService()
    policy_service = LLMAgentPolicyHistoryTrackedService(history_service=history_service)
    policy = policy_service.create("notebook-1", "policy-a", [_rule("r1")])

    exception_service = LLMAgentPolicyExceptionHistoryTrackedService(history_service=history_service)

    exception = exception_service.create(
        "notebook-1", policy.policy_id, {"tool_name": "delete"}, "temporary relief", FUTURE
    )
    exception_service.revoke(exception.exception_id)

    history = history_service.list(policy.policy_id)
    assert [item.change_type for item in history] == [CREATED, EXCEPTION_CREATED, EXCEPTION_REVOKED]
    assert history[1].before is None
    assert history[1].after["reason"] == "temporary relief"
    assert history[1].after["status"] == EXCEPTION_ACTIVE
    assert history[2].after["status"] == "revoked"


def test_historical_lookup_get_at():
    history_service = LLMAgentPolicyHistoryService()

    t0 = datetime.now(timezone.utc)
    t1 = t0 + timedelta(minutes=1)
    t2 = t0 + timedelta(minutes=2)

    history_service.store.save(
        LLMAgentPolicyChange(
            scope_id="notebook-1", policy_id="policy-a", change_type=CREATED,
            before=None, after={"name": "v1"}, created_at=t0,
        )
    )
    history_service.store.save(
        LLMAgentPolicyChange(
            scope_id="notebook-1", policy_id="policy-a", change_type=UPDATED,
            before={"name": "v1"}, after={"name": "v2"}, created_at=t1,
        )
    )
    history_service.store.save(
        LLMAgentPolicyChange(
            scope_id="notebook-1", policy_id="policy-a", change_type=CHANGE_ARCHIVED,
            before={"name": "v2"}, after={"name": "v2", "status": "archived"}, created_at=t2,
        )
    )

    assert history_service.get_at("policy-a", t0 - timedelta(seconds=1)) is None
    assert history_service.get_at("policy-a", t0)["name"] == "v1"
    assert history_service.get_at("policy-a", t1 - timedelta(seconds=1))["name"] == "v1"
    assert history_service.get_at("policy-a", t1)["name"] == "v2"
    assert history_service.get_at("policy-a", t2)["status"] == "archived"
    assert history_service.get_at("policy-a", t2 + timedelta(hours=1))["status"] == "archived"


def test_ordering():
    history_service = LLMAgentPolicyHistoryService()
    service = LLMAgentPolicyHistoryTrackedService(history_service=history_service)
    created = service.create("notebook-1", "policy-a", [_rule("r1")])
    service.update(created.policy_id, name="v2")
    service.update(created.policy_id, name="v3")
    service.archive(created.policy_id)

    history = history_service.list(created.policy_id)
    assert [item.change_type for item in history] == [CREATED, UPDATED, UPDATED, CHANGE_ARCHIVED]
    # strictly non-decreasing created_at, oldest first
    timestamps = [item.created_at for item in history]
    assert timestamps == sorted(timestamps)


def test_scope_isolation():
    history_service = LLMAgentPolicyHistoryService()
    service = LLMAgentPolicyHistoryTrackedService(history_service=history_service)
    policy_1 = service.create("notebook-1", "policy-a", [_rule("r1")])
    policy_2 = service.create("notebook-2", "policy-b", [_rule("r2")])

    scope_1_history = history_service.list_for_scope("notebook-1")
    scope_2_history = history_service.list_for_scope("notebook-2")

    assert [item.policy_id for item in scope_1_history] == [policy_1.policy_id]
    assert [item.policy_id for item in scope_2_history] == [policy_2.policy_id]


def test_immutable_records():
    history_service = LLMAgentPolicyHistoryService()
    change = history_service.record_change(
        "notebook-1", "policy-a", CREATED, before=None, after={"name": "policy-a"}
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        change.change_type = UPDATED

    # mutating a dict returned from get()/list() never affects stored state
    fetched = history_service.get(change.change_id)
    fetched.after["name"] = "tampered"
    refetched = history_service.get(change.change_id)
    assert refetched.after["name"] == "policy-a"


def test_sensitive_data_is_redacted():
    history_service = LLMAgentPolicyHistoryService()
    change = history_service.record_change(
        "notebook-1", "policy-a", CREATED, before=None,
        after={"name": "policy-a", "rules": [{"reason": "api_key: sk-abcdefghijklmnopqrstuvwxyz"}]},
    )

    assert "sk-abcdefghijklmnopqrstuvwxyz" not in str(change.to_dict())
    assert change.after["rules"][0]["reason"] == "[REDACTED]"


def test_invalid_change_arguments():
    history_service = LLMAgentPolicyHistoryService()

    with pytest.raises(InvalidPolicyChangeError):
        history_service.record_change("", "policy-a", CREATED, None, {})
    with pytest.raises(InvalidPolicyChangeError):
        history_service.record_change("notebook-1", "", CREATED, None, {})
    with pytest.raises(InvalidPolicyChangeError):
        history_service.record_change("notebook-1", "policy-a", "not-a-type", None, {})
    with pytest.raises(InvalidPolicyChangeError):
        history_service.record_change("notebook-1", "policy-a", CREATED, "not-a-dict", {})


def test_missing_change():
    history_service = LLMAgentPolicyHistoryService()
    with pytest.raises(UnknownPolicyChangeError):
        history_service.get("missing-id")


def test_history_failure_does_not_change_policy_behavior():
    class BrokenHistoryService(LLMAgentPolicyHistoryService):
        def record_change(self, *args, **kwargs):
            raise RuntimeError("history store is unavailable")

    service = LLMAgentPolicyHistoryTrackedService(history_service=BrokenHistoryService())

    created = service.create("notebook-1", "policy-a", [_rule("r1")])
    assert created.name == "policy-a"

    updated = service.update(created.policy_id, name="renamed")
    assert updated.name == "renamed"

    archived = service.archive(created.policy_id)
    assert archived.status == ARCHIVED
