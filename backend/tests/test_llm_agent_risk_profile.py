import pytest

from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW, LEVEL_MEDIUM
from backend.agent_risk_profile import (
    ACTIVE,
    ARCHIVED,
    ActiveRiskProfileExistsError,
    ArchivedRiskProfileError,
    DuplicateActionRuleIdError,
    InvalidRiskProfileActionRuleError,
    InvalidRiskProfileError,
    InvalidRiskProfileStatusError,
    JsonRiskProfileStore,
    LLMAgentRiskProfile,
    LLMAgentRiskProfileService,
    RiskProfileActionRule,
    RiskProfileResolution,
    UnknownRiskProfileError,
)
from backend.agent_policy_risk_assessment import InvalidActionContextError


def _rule(rule_id, level, match=None, reason=""):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level, reason=reason)


# --- CRUD --------------------------------------------------------------------


def test_create_returns_active_version_one_profile():
    service = LLMAgentRiskProfileService()
    profile = service.create("scope-1", "default-profile", default_level=LEVEL_MEDIUM)

    assert profile.scope_id == "scope-1"
    assert profile.name == "default-profile"
    assert profile.default_level == LEVEL_MEDIUM
    assert profile.status == ACTIVE
    assert profile.version == 1
    assert profile.action_rules == []
    assert profile.profile_id


def test_get_returns_created_profile():
    service = LLMAgentRiskProfileService()
    created = service.create("scope-1", "p1")

    fetched = service.get(created.profile_id)
    assert fetched == created


def test_get_unknown_profile_raises():
    service = LLMAgentRiskProfileService()
    with pytest.raises(UnknownRiskProfileError):
        service.get("does-not-exist")


def test_list_returns_profiles_for_scope_only():
    service = LLMAgentRiskProfileService()
    p1 = service.create("scope-1", "p1")
    service.create("scope-2", "p2")

    result = service.list("scope-1")
    assert [p.profile_id for p in result] == [p1.profile_id]


def test_update_name_only_does_not_bump_version():
    service = LLMAgentRiskProfileService()
    created = service.create("scope-1", "p1")

    updated = service.update(created.profile_id, name="renamed")
    assert updated.name == "renamed"
    assert updated.version == 1


def test_update_action_rules_bumps_version():
    service = LLMAgentRiskProfileService()
    created = service.create("scope-1", "p1")

    updated = service.update(
        created.profile_id, action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete"})]
    )
    assert updated.version == 2
    assert updated.action_rules[0].rule_id == "r1"


def test_update_default_level_bumps_version():
    service = LLMAgentRiskProfileService()
    created = service.create("scope-1", "p1", default_level=LEVEL_LOW)

    updated = service.update(created.profile_id, default_level=LEVEL_HIGH)
    assert updated.version == 2
    assert updated.default_level == LEVEL_HIGH


def test_update_with_identical_action_rules_is_a_noop_on_version():
    service = LLMAgentRiskProfileService()
    rules = [_rule("r1", LEVEL_HIGH, {"tool_name": "delete"})]
    created = service.create("scope-1", "p1", action_rules=rules)

    updated = service.update(created.profile_id, action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete"})])
    assert updated.version == 1


def test_archive_marks_archived_and_is_idempotent():
    service = LLMAgentRiskProfileService()
    created = service.create("scope-1", "p1")

    archived = service.archive(created.profile_id)
    assert archived.status == ARCHIVED

    archived_again = service.archive(created.profile_id)
    assert archived_again.status == ARCHIVED
    assert archived_again.version == archived.version


def test_archive_unknown_profile_raises():
    service = LLMAgentRiskProfileService()
    with pytest.raises(UnknownRiskProfileError):
        service.archive("does-not-exist")


def test_update_archived_profile_raises():
    service = LLMAgentRiskProfileService()
    created = service.create("scope-1", "p1")
    service.archive(created.profile_id)

    with pytest.raises(ArchivedRiskProfileError):
        service.update(created.profile_id, name="renamed")


# --- validation ----------------------------------------------------------


def test_create_requires_scope_id():
    service = LLMAgentRiskProfileService()
    with pytest.raises(InvalidRiskProfileError):
        service.create("", "p1")


def test_create_requires_name():
    service = LLMAgentRiskProfileService()
    with pytest.raises(InvalidRiskProfileError):
        service.create("scope-1", "")


def test_create_rejects_invalid_default_level():
    service = LLMAgentRiskProfileService()
    with pytest.raises(InvalidRiskProfileError):
        service.create("scope-1", "p1", default_level="NOT_A_LEVEL")


def test_create_rejects_invalid_status():
    service = LLMAgentRiskProfileService()
    with pytest.raises(InvalidRiskProfileStatusError):
        service.create("scope-1", "p1", status="pending")


def test_create_rejects_action_rules_that_are_not_a_list():
    service = LLMAgentRiskProfileService()
    with pytest.raises(InvalidRiskProfileError):
        service.create("scope-1", "p1", action_rules={"rule_id": "r1"})


def test_action_rule_rejects_invalid_level():
    with pytest.raises(InvalidRiskProfileActionRuleError):
        RiskProfileActionRule(rule_id="r1", level="NOT_A_LEVEL")


def test_action_rule_rejects_blank_rule_id():
    with pytest.raises(InvalidRiskProfileActionRuleError):
        RiskProfileActionRule(rule_id="", level=LEVEL_HIGH)


def test_action_rule_rejects_non_dict_match():
    with pytest.raises(InvalidRiskProfileActionRuleError):
        RiskProfileActionRule(rule_id="r1", match="not-a-dict", level=LEVEL_HIGH)


def test_duplicate_rule_id_within_profile_rejected():
    service = LLMAgentRiskProfileService()
    with pytest.raises(DuplicateActionRuleIdError):
        service.create(
            "scope-1",
            "p1",
            action_rules=[
                _rule("dup", LEVEL_HIGH, {"tool_name": "a"}),
                _rule("dup", LEVEL_LOW, {"tool_name": "b"}),
            ],
        )


def test_only_one_active_profile_per_scope():
    service = LLMAgentRiskProfileService()
    service.create("scope-1", "p1")

    with pytest.raises(ActiveRiskProfileExistsError):
        service.create("scope-1", "p2")


def test_creating_archived_profile_alongside_active_one_is_allowed():
    service = LLMAgentRiskProfileService()
    service.create("scope-1", "p1")

    archived_from_start = service.create("scope-1", "p2", status=ARCHIVED)
    assert archived_from_start.status == ARCHIVED


def test_creating_active_profile_allowed_after_archiving_prior_one():
    service = LLMAgentRiskProfileService()
    first = service.create("scope-1", "p1")
    service.archive(first.profile_id)

    second = service.create("scope-1", "p2")
    assert second.status == ACTIVE


# --- action/profile resolution -----------------------------------------


def test_resolve_matches_first_matching_action_rule():
    service = LLMAgentRiskProfileService()
    service.create(
        "scope-1",
        "p1",
        default_level=LEVEL_LOW,
        action_rules=[
            _rule("delete-rule", LEVEL_CRITICAL, {"tool_name": "delete_file"}, reason="deletes are critical"),
            _rule("write-rule", LEVEL_MEDIUM, {"tool_name": "write_file"}),
        ],
    )

    resolution = service.resolve("scope-1", {"tool_name": "delete_file"})
    assert isinstance(resolution, RiskProfileResolution)
    assert resolution.level == LEVEL_CRITICAL
    assert resolution.matched_rule_id == "delete-rule"
    assert resolution.reason == "deletes are critical"
    assert resolution.scope_id == "scope-1"


def test_resolve_falls_back_to_default_level_when_no_rule_matches():
    service = LLMAgentRiskProfileService()
    service.create(
        "scope-1",
        "p1",
        default_level=LEVEL_MEDIUM,
        action_rules=[_rule("delete-rule", LEVEL_CRITICAL, {"tool_name": "delete_file"})],
    )

    resolution = service.resolve("scope-1", {"tool_name": "read_file"})
    assert resolution.level == LEVEL_MEDIUM
    assert resolution.matched_rule_id is None


def test_resolve_first_matching_rule_wins_when_multiple_match():
    service = LLMAgentRiskProfileService()
    service.create(
        "scope-1",
        "p1",
        action_rules=[
            _rule("first", LEVEL_HIGH, {"subject": "prod"}),
            _rule("second", LEVEL_CRITICAL, {"subject": "prod"}),
        ],
    )

    resolution = service.resolve("scope-1", {"subject": "prod"})
    assert resolution.matched_rule_id == "first"
    assert resolution.level == LEVEL_HIGH


def test_resolve_match_supports_list_of_acceptable_values():
    service = LLMAgentRiskProfileService()
    service.create(
        "scope-1",
        "p1",
        action_rules=[_rule("multi", LEVEL_HIGH, {"tool_name": ["delete_file", "drop_table"]})],
    )

    assert service.resolve("scope-1", {"tool_name": "drop_table"}).level == LEVEL_HIGH
    assert service.resolve("scope-1", {"tool_name": "read_file"}).matched_rule_id is None


def test_resolve_provenance_embeds_profile_and_action_context():
    service = LLMAgentRiskProfileService()
    profile = service.create("scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete"})])

    action_context = {"tool_name": "delete", "arguments": {"path": "/tmp/x"}}
    resolution = service.resolve("scope-1", action_context)

    assert resolution.provenance["profile"].profile_id == profile.profile_id
    assert resolution.provenance["action_context"] == action_context
    assert resolution.provenance["action_context"] is not action_context
    assert resolution.version == profile.version


def test_resolve_rejects_non_dict_action_context():
    service = LLMAgentRiskProfileService()
    service.create("scope-1", "p1")
    with pytest.raises(InvalidActionContextError):
        service.resolve("scope-1", "not-a-dict")


def test_resolve_requires_scope_id():
    service = LLMAgentRiskProfileService()
    with pytest.raises(InvalidRiskProfileError):
        service.resolve("", {"tool_name": "delete"})


# --- scope isolation -------------------------------------------------------


def test_resolve_is_scope_isolated():
    service = LLMAgentRiskProfileService()
    service.create("scope-1", "p1", default_level=LEVEL_CRITICAL)
    service.create("scope-2", "p2", default_level=LEVEL_LOW)

    assert service.resolve("scope-1", {}).level == LEVEL_CRITICAL
    assert service.resolve("scope-2", {}).level == LEVEL_LOW


def test_list_and_active_profile_limit_are_scope_isolated():
    service = LLMAgentRiskProfileService()
    service.create("scope-1", "p1")
    service.create("scope-2", "p2")

    # Scope-1 already has an active profile; scope-2's own active profile
    # must never block a second active profile for a *different* scope.
    assert len(service.list("scope-1")) == 1
    assert len(service.list("scope-2")) == 1


# --- archived profile -------------------------------------------------------


def test_archived_profile_never_selected_by_resolve():
    service = LLMAgentRiskProfileService()
    created = service.create("scope-1", "p1", default_level=LEVEL_CRITICAL)
    service.archive(created.profile_id)

    assert service.resolve("scope-1", {}) is None


# --- version handling --------------------------------------------------


def test_version_increments_across_multiple_content_updates():
    service = LLMAgentRiskProfileService()
    created = service.create("scope-1", "p1")

    v2 = service.update(created.profile_id, default_level=LEVEL_MEDIUM)
    v3 = service.update(v2.profile_id, action_rules=[_rule("r1", LEVEL_HIGH)])

    assert v2.version == 2
    assert v3.version == 3


def test_resolve_reports_current_version_after_update():
    service = LLMAgentRiskProfileService()
    created = service.create("scope-1", "p1", default_level=LEVEL_LOW)
    service.update(created.profile_id, default_level=LEVEL_HIGH)

    resolution = service.resolve("scope-1", {})
    assert resolution.level == LEVEL_HIGH
    assert resolution.version == 2


# --- default fallback (no matching profile) -----------------------------


def test_resolve_returns_none_when_scope_has_no_profile_at_all():
    service = LLMAgentRiskProfileService()
    assert service.resolve("never-configured-scope", {"tool_name": "delete"}) is None


def test_default_risk_behavior_unaffected_when_no_profile_configured():
    from backend.agent_policy_decision import LLMAgentPolicyDecisionEngine
    from backend.agent_policy_engine import ALLOW as POLICY_ALLOW
    from backend.agent_policy_engine import LLMAgentPolicyRule, LLMAgentPolicyService
    from backend.agent_policy_enforcement import LLMAgentPolicyEnforcement
    from backend.agent_policy_resolution import LLMAgentPolicyResolver
    from backend.agent_policy_risk_assessment import LLMAgentPolicyRiskAssessor

    policy_service = LLMAgentPolicyService()
    policy_service.create(
        "scope-1", "allow-all", [LLMAgentPolicyRule(rule_id="allow", effect=POLICY_ALLOW, match={})]
    )
    resolver = LLMAgentPolicyResolver(policy_service)
    enforcement = LLMAgentPolicyEnforcement(resolver, LLMAgentPolicyDecisionEngine())
    assessor = LLMAgentPolicyRiskAssessor(enforcement)

    profile_service = LLMAgentRiskProfileService()
    assert profile_service.resolve("scope-1", {"scope_id": "scope-1", "tool_name": "noop"}) is None

    assessment = assessor.assess({"scope_id": "scope-1", "tool_name": "noop", "arguments": {}})
    assert assessment.risk_level == LEVEL_LOW


# --- provenance --------------------------------------------------------


def test_provenance_traces_back_to_matched_rule_and_profile_version():
    service = LLMAgentRiskProfileService()
    profile = service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete"}, reason="dangerous")]
    )
    updated = service.update(profile.profile_id, name="renamed")

    resolution = service.resolve("scope-1", {"tool_name": "delete"})
    assert resolution.profile_id == updated.profile_id
    assert resolution.version == updated.version
    assert resolution.matched_rule_id == "r1"
    assert resolution.reason == "dangerous"
    assert resolution.provenance["profile"].name == "renamed"


def test_provenance_default_level_reason_names_profile():
    service = LLMAgentRiskProfileService()
    profile = service.create("scope-1", "p1", default_level=LEVEL_MEDIUM)

    resolution = service.resolve("scope-1", {"tool_name": "anything"})
    assert profile.profile_id in resolution.reason
    assert resolution.matched_rule_id is None


# --- persistence backends ------------------------------------------------


def test_json_store_round_trips_across_service_instances(tmp_path):
    path = tmp_path / "risk_profiles.json"

    service1 = LLMAgentRiskProfileService(store=JsonRiskProfileStore(path))
    created = service1.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete"})], default_level=LEVEL_LOW
    )

    service2 = LLMAgentRiskProfileService(store=JsonRiskProfileStore(path))
    fetched = service2.get(created.profile_id)
    assert fetched.name == "p1"
    assert fetched.action_rules[0].rule_id == "r1"

    resolution = service2.resolve("scope-1", {"tool_name": "delete"})
    assert resolution.level == LEVEL_HIGH
