import pytest

from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW
from backend.agent_risk_profile import (
    ARCHIVED,
    LLMAgentRiskProfile,
    LLMAgentRiskProfileService,
    RiskProfileActionRule,
)
from backend.agent_risk_profile_validation import LLMAgentRiskProfileValidator, ValidationResult


@pytest.fixture
def validator():
    return LLMAgentRiskProfileValidator()


def _rule(rule_id="r1", level=LEVEL_HIGH, match=None):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level)


# --- valid profile -----------------------------------------------------


def test_valid_profile_reports_no_issues(validator):
    profile = LLMAgentRiskProfile(
        scope_id="scope-1",
        name="p1",
        action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})],
        default_level=LEVEL_LOW,
    )
    result = validator.validate(profile)
    assert isinstance(result, ValidationResult)
    assert result.is_valid
    assert result.issues == []


def test_real_service_created_profile_is_always_valid(validator):
    service = LLMAgentRiskProfileService()
    profile = service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    assert validator.validate(profile).is_valid


def test_invalid_profile_type_reports_single_issue(validator):
    result = validator.validate({"scope_id": "scope-1"})
    assert not result.is_valid
    assert result.issues[0].code == "invalid_profile_type"


# --- missing fields ------------------------------------------------------


def test_missing_scope_id_reported(validator):
    profile = LLMAgentRiskProfile(scope_id="", name="p1")
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "missing_scope_id" and issue.path == "scope_id" for issue in result.issues)


def test_missing_name_reported(validator):
    profile = LLMAgentRiskProfile(scope_id="scope-1", name="")
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "missing_name" and issue.path == "name" for issue in result.issues)


def test_multiple_missing_fields_all_reported_in_one_pass(validator):
    profile = LLMAgentRiskProfile(scope_id="", name="")
    result = validator.validate(profile)
    codes = {issue.code for issue in result.issues}
    assert {"missing_scope_id", "missing_name"} <= codes


# --- invalid risk level --------------------------------------------------


def test_invalid_default_level_reported(validator):
    profile = LLMAgentRiskProfile(scope_id="scope-1", name="p1", default_level="NOT_A_LEVEL")
    result = validator.validate(profile)
    assert not result.is_valid
    issue = next(issue for issue in result.issues if issue.path == "default_level")
    assert issue.code == "unknown_risk_level"


def test_invalid_action_rule_level_reported():
    # Bypass RiskProfileActionRule's own __post_init__ validation by
    # embedding a raw dict directly into action_rules, the same
    # hand-built/untrusted-input scenario the validator exists for.
    profile = LLMAgentRiskProfile(
        scope_id="scope-1", name="p1", action_rules=[{"rule_id": "r1", "match": {}, "level": "BOGUS"}]
    )
    result = LLMAgentRiskProfileValidator().validate(profile)
    assert not result.is_valid
    issue = next(issue for issue in result.issues if issue.path == "action_rules[0].level")
    assert issue.code == "unknown_risk_level"


# --- unknown factor/rule -------------------------------------------------


def test_unknown_risk_level_in_multiple_rules_all_reported(validator):
    profile = LLMAgentRiskProfile(
        scope_id="scope-1",
        name="p1",
        action_rules=[
            {"rule_id": "r1", "match": {}, "level": "MADE_UP"},
            {"rule_id": "r2", "match": {}, "level": "ALSO_MADE_UP"},
        ],
    )
    result = validator.validate(profile)
    unknown_level_paths = {issue.path for issue in result.issues if issue.code == "unknown_risk_level"}
    assert unknown_level_paths == {"action_rules[0].level", "action_rules[1].level"}


def test_duplicate_rule_id_reported(validator):
    profile = LLMAgentRiskProfile(
        scope_id="scope-1",
        name="p1",
        action_rules=[_rule("dup", LEVEL_HIGH, {"tool_name": "a"}), _rule("dup", LEVEL_LOW, {"tool_name": "b"})],
    )
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "duplicate_rule_id" and issue.path == "action_rules[1].rule_id" for issue in result.issues)


# --- malformed action rule ------------------------------------------------


def test_malformed_action_rule_missing_rule_id_reported(validator):
    profile = LLMAgentRiskProfile(scope_id="scope-1", name="p1", action_rules=[{"match": {}, "level": LEVEL_HIGH}])
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "malformed_action_rule" and issue.path == "action_rules[0]" for issue in result.issues)


def test_action_rule_with_non_dict_match_reported(validator):
    profile = LLMAgentRiskProfile(
        scope_id="scope-1", name="p1", action_rules=[{"rule_id": "r1", "match": "not-a-dict", "level": LEVEL_HIGH}]
    )
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "malformed_action_rule" for issue in result.issues)


def test_action_rule_wrong_type_reported(validator):
    profile = LLMAgentRiskProfile(scope_id="scope-1", name="p1", action_rules=["not-a-rule-at-all"])
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "invalid_action_rule_type" and issue.path == "action_rules[0]" for issue in result.issues)


def test_action_rules_wrong_container_type_reported(validator):
    profile = LLMAgentRiskProfile(scope_id="scope-1", name="p1", action_rules="not-a-list")
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "invalid_action_rules_type" and issue.path == "action_rules" for issue in result.issues)


# --- invalid version/status ------------------------------------------------


def test_invalid_status_reported(validator):
    profile = LLMAgentRiskProfile(scope_id="scope-1", name="p1", status="pending")
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "invalid_status" and issue.path == "status" for issue in result.issues)


def test_archived_status_is_a_structurally_valid_status(validator):
    profile = LLMAgentRiskProfile(scope_id="scope-1", name="p1", status=ARCHIVED)
    result = validator.validate(profile)
    assert result.is_valid


@pytest.mark.parametrize("version", [0, -1, "1", 1.5, True])
def test_invalid_version_reported(validator, version):
    profile = LLMAgentRiskProfile(scope_id="scope-1", name="p1", version=version)
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "invalid_version" and issue.path == "version" for issue in result.issues)


def test_conflicting_action_binding_reported(validator):
    profile = LLMAgentRiskProfile(
        scope_id="scope-1", name="p1", action_name="delete_file", action_category="destructive"
    )
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "conflicting_action_binding" for issue in result.issues)


def test_blank_action_name_reported(validator):
    profile = LLMAgentRiskProfile(scope_id="scope-1", name="p1", action_name="   ")
    result = validator.validate(profile)
    assert not result.is_valid
    assert any(issue.code == "invalid_action_name" for issue in result.issues)


# --- resolution integration ------------------------------------------------


def test_validate_action_rules_valid_profile_matching_rule(validator):
    profile = LLMAgentRiskProfile(
        scope_id="scope-1",
        name="p1",
        action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})],
        default_level=LEVEL_LOW,
    )
    result = validator.validate_action_rules(profile, {"tool_name": "delete_file"})
    assert result.is_valid


def test_validate_action_rules_valid_profile_default_fallback(validator):
    profile = LLMAgentRiskProfile(
        scope_id="scope-1",
        name="p1",
        action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})],
        default_level=LEVEL_LOW,
    )
    result = validator.validate_action_rules(profile, {"tool_name": "read_file"})
    assert result.is_valid


def test_validate_action_rules_structurally_invalid_profile_short_circuits(validator):
    # A malformed action_rule would crash a naive resolve_level() call --
    # validate_action_rules() must report the structural issue instead
    # of attempting to resolve at all.
    profile = LLMAgentRiskProfile(
        scope_id="scope-1", name="p1", action_rules=[{"rule_id": "r1", "match": {}, "level": "BOGUS"}]
    )
    result = validator.validate_action_rules(profile, {"tool_name": "delete_file"})
    assert not result.is_valid
    assert any(issue.code == "unknown_risk_level" for issue in result.issues)


def test_validate_action_rules_invalid_action_context_reported_not_raised(validator):
    profile = LLMAgentRiskProfile(scope_id="scope-1", name="p1")
    result = validator.validate_action_rules(profile, "not-a-dict")
    assert not result.is_valid
    assert result.issues[0].code == "invalid_action_context_type"


def test_validate_action_rules_agrees_with_real_end_to_end_resolution(validator):
    from backend.agent_risk_profile_resolution import LLMAgentRiskProfileResolver

    service = LLMAgentRiskProfileService()
    profile = service.create(
        "scope-1",
        "p1",
        action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})],
        default_level=LEVEL_LOW,
    )
    resolver = LLMAgentRiskProfileResolver(service)

    action_context = {"tool_name": "delete_file"}
    resolved = resolver.resolve("scope-1", action_context)
    result = validator.validate_action_rules(profile, action_context)

    assert result.is_valid
    assert resolved.level == LEVEL_CRITICAL


def test_validate_action_rules_invalid_profile_type_reported(validator):
    result = validator.validate_action_rules("not-a-profile", {})
    assert not result.is_valid
    assert result.issues[0].code == "invalid_profile_type"
