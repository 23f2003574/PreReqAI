from datetime import datetime, timedelta, timezone

import pytest

from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW
from backend.agent_risk_profile import ARCHIVED, LLMAgentRiskProfileService, RiskProfileActionRule
from backend.agent_risk_profile_activation import LLMAgentRiskProfileActivationService
from backend.agent_risk_profile_history import (
    ACTIVATED,
    ARCHIVED as CHANGE_ARCHIVED,
    CREATED,
    DEACTIVATED,
    UPDATED,
    InvalidRiskProfileChangeError,
    JsonRiskProfileHistoryStore,
    LLMAgentRiskProfileActivationHistoryTrackedService,
    LLMAgentRiskProfileChange,
    LLMAgentRiskProfileHistoryService,
    LLMAgentRiskProfileHistoryTrackedService,
    UnknownRiskProfileChangeError,
)
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService


def _rule(rule_id, level, match=None):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level)


# --- create/update history ---------------------------------------------


def test_create_records_a_created_change():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service, actor="alice")

    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)

    changes = history_service.list(profile.profile_id)
    assert len(changes) == 1
    assert changes[0].change_type == CREATED
    assert changes[0].before is None
    assert changes[0].after["profile_id"] == profile.profile_id
    assert changes[0].version == 1
    assert changes[0].actor == "alice"


def test_update_records_an_updated_change_only_when_meaningful():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    profile = profile_service.create("scope-1", "p1")
    profile_service.update(profile.profile_id, action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})])
    # A no-op update (identical rules) must not add a second entry.
    profile_service.update(profile.profile_id, action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})])

    changes = history_service.list(profile.profile_id)
    assert [change.change_type for change in changes] == [CREATED, UPDATED]
    assert changes[1].version == 2
    assert changes[1].after["action_rules"][0]["rule_id"] == "r1"


def test_archive_records_an_archived_change():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    profile = profile_service.create("scope-1", "p1")
    profile_service.archive(profile.profile_id)
    # idempotent re-archive must not add a second entry
    profile_service.archive(profile.profile_id)

    changes = history_service.list(profile.profile_id)
    assert [change.change_type for change in changes] == [CREATED, CHANGE_ARCHIVED]
    assert changes[1].after["status"] == ARCHIVED


def test_name_only_update_is_still_a_meaningful_history_event():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    profile = profile_service.create("scope-1", "p1")
    profile_service.update(profile.profile_id, name="renamed")

    # Commit #1's own version-bump rule (name-only edits never bump
    # version) is a narrower concern than "worth recording in history" --
    # a rename is still a real, auditable change to the profile record
    # (the to_dict() snapshot genuinely differs once updated_at is
    # excluded), even though profile.version itself stays 1.
    changes = history_service.list(profile.profile_id)
    assert [change.change_type for change in changes] == [CREATED, UPDATED]
    assert changes[1].version == 1
    assert changes[1].after["name"] == "renamed"


def test_repeating_the_same_rename_is_not_recorded_again():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    profile = profile_service.create("scope-1", "p1")
    profile_service.update(profile.profile_id, name="renamed")
    profile_service.update(profile.profile_id, name="renamed")

    changes = history_service.list(profile.profile_id)
    assert [change.change_type for change in changes] == [CREATED, UPDATED]


# --- activation/deactivation history ------------------------------------


def _activation_services(actor="ops"):
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    activation_service = LLMAgentRiskProfileActivationHistoryTrackedService(
        profile_service, version_service, history_service=history_service, actor=actor
    )
    return history_service, profile_service, version_service, activation_service


def test_activation_records_an_activated_change():
    history_service, profile_service, version_service, activation_service = _activation_services()

    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)

    activation_service.activate(profile.profile_id, 1, "scope-1", reason="rollback to conservative default")

    changes = history_service.list(profile.profile_id)
    assert [change.change_type for change in changes] == [ACTIVATED]
    assert changes[0].reason == "rollback to conservative default"
    assert changes[0].after["default_level"] == LEVEL_LOW
    assert changes[0].actor == "ops"


def test_idempotent_activation_records_nothing():
    history_service, profile_service, version_service, activation_service = _activation_services()

    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    activation_service.activate(profile.profile_id, 1, "scope-1")  # already current -- ALREADY_ACTIVE

    assert history_service.list(profile.profile_id) == []


def test_deactivation_records_a_deactivated_change():
    history_service, profile_service, version_service, activation_service = _activation_services()

    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    activation_service.deactivate(profile.profile_id, "scope-1")
    # idempotent re-deactivation must not add a second entry
    activation_service.deactivate(profile.profile_id, "scope-1")

    changes = history_service.list(profile.profile_id)
    assert [change.change_type for change in changes] == [DEACTIVATED]
    assert changes[0].after["status"] == ARCHIVED


def test_full_stack_composition_records_both_update_and_activation_events():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service, actor="alice")
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    activation_service = LLMAgentRiskProfileActivationHistoryTrackedService(
        profile_service, version_service, history_service=history_service, actor="ops"
    )

    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1, no extra UPDATED (identical to create())
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)  # v2 -> UPDATED
    activation_service.activate(profile.profile_id, 1, "scope-1")  # restores v1 -> UPDATED + ACTIVATED

    changes = history_service.list(profile.profile_id)
    assert [change.change_type for change in changes] == [CREATED, UPDATED, UPDATED, ACTIVATED]
    assert changes[-1].actor == "ops"
    assert changes[-2].actor == "alice"


# --- chronological retrieval ---------------------------------------------


def test_list_returns_changes_oldest_first():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    profile = profile_service.create("scope-1", "p1")
    profile_service.update(profile.profile_id, default_level=LEVEL_HIGH)
    profile_service.archive(profile.profile_id)

    changes = history_service.list(profile.profile_id)
    assert [change.change_type for change in changes] == [CREATED, UPDATED, CHANGE_ARCHIVED]
    timestamps = [change.created_at for change in changes]
    assert timestamps == sorted(timestamps)


# --- historical lookup -----------------------------------------------------


def test_get_at_reconstructs_applicable_snapshot():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    t1 = datetime.now(timezone.utc)
    profile_service.update(profile.profile_id, default_level=LEVEL_CRITICAL)
    t2 = datetime.now(timezone.utc)

    assert history_service.get_at(profile.profile_id, t1)["default_level"] == LEVEL_LOW
    assert history_service.get_at(profile.profile_id, t2)["default_level"] == LEVEL_CRITICAL


def test_get_at_before_creation_returns_none():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    before_anything = datetime.now(timezone.utc) - timedelta(days=1)
    profile = profile_service.create("scope-1", "p1")

    assert history_service.get_at(profile.profile_id, before_anything) is None


def test_get_at_requires_datetime():
    history_service = LLMAgentRiskProfileHistoryService()
    with pytest.raises(InvalidRiskProfileChangeError):
        history_service.get_at("profile-1", "not-a-datetime")


def test_get_at_never_mutates_current_state():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    profile_service.update(profile.profile_id, default_level=LEVEL_HIGH)

    history_service.get_at(profile.profile_id, datetime.now(timezone.utc))

    live = profile_service.get(profile.profile_id)
    assert live.default_level == LEVEL_HIGH


# --- scope isolation --------------------------------------------------


def test_list_for_scope_is_isolated():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    p1 = profile_service.create("scope-1", "p1")
    p2 = profile_service.create("scope-2", "p2")

    scope1_changes = history_service.list_for_scope("scope-1")
    scope2_changes = history_service.list_for_scope("scope-2")

    assert [change.profile_id for change in scope1_changes] == [p1.profile_id]
    assert [change.profile_id for change in scope2_changes] == [p2.profile_id]


def test_list_is_isolated_per_profile():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    p1 = profile_service.create("scope-1", "p1")
    p2 = profile_service.create("scope-1", "p2", status=ARCHIVED)

    assert len(history_service.list(p1.profile_id)) == 1
    assert len(history_service.list(p2.profile_id)) == 1
    assert history_service.list(p1.profile_id)[0].profile_id == p1.profile_id


# --- immutability --------------------------------------------------------


def test_change_record_is_frozen():
    change = LLMAgentRiskProfileChange(
        scope_id="s", profile_id="p", version=1, change_type=CREATED, before=None, after={}
    )
    with pytest.raises(Exception):
        change.version = 2


def test_get_returns_same_change_every_time():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    profile = profile_service.create("scope-1", "p1")
    recorded = history_service.list(profile.profile_id)[0]

    fetched_once = history_service.get(recorded.change_id)
    fetched_twice = history_service.get(recorded.change_id)
    assert fetched_once == fetched_twice == recorded


def test_get_unknown_change_raises():
    history_service = LLMAgentRiskProfileHistoryService()
    with pytest.raises(UnknownRiskProfileChangeError):
        history_service.get("does-not-exist")


# --- provenance ----------------------------------------------------------


def test_before_is_none_only_for_created():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service)

    profile = profile_service.create("scope-1", "p1")
    profile_service.update(profile.profile_id, default_level=LEVEL_HIGH)

    changes = history_service.list(profile.profile_id)
    assert changes[0].before is None
    assert changes[1].before is not None
    assert changes[1].before["default_level"] == LEVEL_LOW


def test_secret_looking_reason_is_redacted():
    history_service = LLMAgentRiskProfileHistoryService()
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    activation_service = LLMAgentRiskProfileActivationHistoryTrackedService(
        profile_service, version_service, history_service=history_service
    )

    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)

    activation_service.activate(
        profile.profile_id, 1, "scope-1", reason="api_key=sk-abcdefghijklmnopqrstuvwx rollback"
    )

    change = history_service.list(profile.profile_id)[0]
    assert "sk-abcdefghijklmnopqrstuvwx" not in change.reason
    assert "[REDACTED]" in change.reason


def test_record_change_rejects_invalid_arguments():
    history_service = LLMAgentRiskProfileHistoryService()
    with pytest.raises(InvalidRiskProfileChangeError):
        history_service.record_change("", "p1", CREATED, 1, before=None, after={})
    with pytest.raises(InvalidRiskProfileChangeError):
        history_service.record_change("s1", "p1", "not-a-type", 1, before=None, after={})
    with pytest.raises(InvalidRiskProfileChangeError):
        history_service.record_change("s1", "p1", CREATED, 0, before=None, after={})


# --- persistence backends -------------------------------------------------


def test_json_store_round_trips_across_service_instances(tmp_path):
    path = tmp_path / "risk_profile_history.json"
    history_service1 = LLMAgentRiskProfileHistoryService(store=JsonRiskProfileHistoryStore(path))
    profile_service = LLMAgentRiskProfileHistoryTrackedService(history_service=history_service1)
    profile = profile_service.create("scope-1", "p1")

    history_service2 = LLMAgentRiskProfileHistoryService(store=JsonRiskProfileHistoryStore(path))
    changes = history_service2.list(profile.profile_id)
    assert len(changes) == 1
    assert changes[0].change_type == CREATED
