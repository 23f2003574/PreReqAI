import pytest

from backend.agent_policy_risk_assessment import InvalidActionContextError
from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW, LEVEL_MEDIUM
from backend.agent_risk_profile import (
    ActiveRiskProfileExistsError,
    InvalidRiskProfileError,
    LLMAgentRiskProfileService,
    RiskProfileActionRule,
)
from backend.agent_risk_profile_resolution import (
    TIER_ACTION_CATEGORY,
    TIER_EXACT_ACTION,
    TIER_SCOPE_DEFAULT,
    LLMAgentRiskProfileResolver,
    ResolvedRiskProfile,
)


def _rule(rule_id, level, match=None, reason=""):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level, reason=reason)


@pytest.fixture
def service():
    return LLMAgentRiskProfileService()


@pytest.fixture
def resolver(service):
    return LLMAgentRiskProfileResolver(service)


# --- exact match -----------------------------------------------------------


def test_exact_action_profile_wins_over_everything(service, resolver):
    service.create("scope-1", "default", default_level=LEVEL_LOW)
    service.create("scope-1", "category-profile", action_category="destructive", default_level=LEVEL_MEDIUM)
    service.create("scope-1", "exact-profile", action_name="delete_file", default_level=LEVEL_CRITICAL)

    result = resolver.resolve("scope-1", {"tool_name": "delete_file", "category": "destructive"})

    assert isinstance(result, ResolvedRiskProfile)
    assert result.tier == TIER_EXACT_ACTION
    assert result.level == LEVEL_CRITICAL
    assert result.profile.name == "exact-profile"


def test_exact_action_profile_uses_own_action_rules():
    service = LLMAgentRiskProfileService()
    resolver = LLMAgentRiskProfileResolver(service)
    service.create(
        "scope-1",
        "exact-profile",
        action_name="delete_file",
        default_level=LEVEL_LOW,
        action_rules=[_rule("r1", LEVEL_CRITICAL, {"subject": "prod"}, reason="prod deletes are critical")],
    )

    prod_result = resolver.resolve("scope-1", {"tool_name": "delete_file", "subject": "prod"})
    assert prod_result.level == LEVEL_CRITICAL
    assert prod_result.matched_rule_id == "r1"

    dev_result = resolver.resolve("scope-1", {"tool_name": "delete_file", "subject": "dev"})
    assert dev_result.level == LEVEL_LOW
    assert dev_result.matched_rule_id is None


# --- category match ----------------------------------------------------


def test_category_profile_used_when_no_exact_action_profile(service, resolver):
    service.create("scope-1", "default", default_level=LEVEL_LOW)
    service.create("scope-1", "category-profile", action_category="destructive", default_level=LEVEL_HIGH)

    result = resolver.resolve("scope-1", {"tool_name": "drop_table", "category": "destructive"})
    assert result.tier == TIER_ACTION_CATEGORY
    assert result.level == LEVEL_HIGH
    assert result.profile.name == "category-profile"


def test_category_profile_ignored_when_action_context_has_no_category(service, resolver):
    service.create("scope-1", "default", default_level=LEVEL_LOW)
    service.create("scope-1", "category-profile", action_category="destructive", default_level=LEVEL_HIGH)

    result = resolver.resolve("scope-1", {"tool_name": "read_file"})
    assert result.tier == TIER_SCOPE_DEFAULT
    assert result.level == LEVEL_LOW


# --- default fallback ----------------------------------------------------


def test_scope_default_used_when_nothing_more_specific_applies(service, resolver):
    service.create("scope-1", "default", default_level=LEVEL_MEDIUM)

    result = resolver.resolve("scope-1", {"tool_name": "read_file", "category": "benign"})
    assert result.tier == TIER_SCOPE_DEFAULT
    assert result.level == LEVEL_MEDIUM
    assert result.matched_rule_id is None


def test_returns_none_when_scope_has_no_profile_at_all(resolver):
    assert resolver.resolve("never-configured-scope", {"tool_name": "delete_file"}) is None


# --- competing profiles --------------------------------------------------


def test_competing_profiles_resolved_by_specificity_not_creation_order(service, resolver):
    # Deliberately create the more specific profiles *before* the default,
    # to prove tier precedence -- not creation order -- decides.
    service.create("scope-1", "exact-profile", action_name="delete_file", default_level=LEVEL_CRITICAL)
    service.create("scope-1", "category-profile", action_category="write", default_level=LEVEL_HIGH)
    service.create("scope-1", "default", default_level=LEVEL_LOW)

    assert resolver.resolve("scope-1", {"tool_name": "delete_file", "category": "write"}).tier == TIER_EXACT_ACTION
    assert resolver.resolve("scope-1", {"tool_name": "update_file", "category": "write"}).tier == TIER_ACTION_CATEGORY
    assert resolver.resolve("scope-1", {"tool_name": "read_file", "category": "benign"}).tier == TIER_SCOPE_DEFAULT


def test_two_exact_action_profiles_for_different_actions_do_not_conflict(service, resolver):
    service.create("scope-1", "delete-profile", action_name="delete_file", default_level=LEVEL_CRITICAL)
    service.create("scope-1", "write-profile", action_name="write_file", default_level=LEVEL_MEDIUM)

    assert resolver.resolve("scope-1", {"tool_name": "delete_file"}).level == LEVEL_CRITICAL
    assert resolver.resolve("scope-1", {"tool_name": "write_file"}).level == LEVEL_MEDIUM


def test_duplicate_active_profile_for_same_exact_action_rejected(service):
    service.create("scope-1", "p1", action_name="delete_file")
    with pytest.raises(ActiveRiskProfileExistsError):
        service.create("scope-1", "p2", action_name="delete_file")


def test_duplicate_active_profile_for_same_action_category_rejected(service):
    service.create("scope-1", "p1", action_category="destructive")
    with pytest.raises(ActiveRiskProfileExistsError):
        service.create("scope-1", "p2", action_category="destructive")


def test_action_name_and_action_category_together_rejected(service):
    with pytest.raises(InvalidRiskProfileError):
        service.create("scope-1", "p1", action_name="delete_file", action_category="destructive")


# --- archived profile ------------------------------------------------------


def test_archived_exact_action_profile_excluded_falls_back_to_category(service, resolver):
    service.create("scope-1", "category-profile", action_category="destructive", default_level=LEVEL_HIGH)
    exact = service.create("scope-1", "exact-profile", action_name="delete_file", default_level=LEVEL_CRITICAL)
    service.archive(exact.profile_id)

    result = resolver.resolve("scope-1", {"tool_name": "delete_file", "category": "destructive"})
    assert result.tier == TIER_ACTION_CATEGORY
    assert result.level == LEVEL_HIGH


def test_archived_default_profile_excluded_returns_none(service, resolver):
    default = service.create("scope-1", "default", default_level=LEVEL_HIGH)
    service.archive(default.profile_id)

    assert resolver.resolve("scope-1", {"tool_name": "anything"}) is None


def test_archiving_and_recreating_frees_the_specificity_key(service):
    first = service.create("scope-1", "p1", action_name="delete_file")
    service.archive(first.profile_id)

    second = service.create("scope-1", "p2", action_name="delete_file")
    assert second.status == "active"


# --- scope isolation --------------------------------------------------


def test_resolution_is_scope_isolated(service, resolver):
    service.create("scope-1", "p1", action_name="delete_file", default_level=LEVEL_CRITICAL)
    service.create("scope-2", "p2", action_name="delete_file", default_level=LEVEL_LOW)

    assert resolver.resolve("scope-1", {"tool_name": "delete_file"}).level == LEVEL_CRITICAL
    assert resolver.resolve("scope-2", {"tool_name": "delete_file"}).level == LEVEL_LOW


def test_profile_in_one_scope_never_leaks_into_another(service, resolver):
    service.create("scope-1", "p1", action_category="destructive", default_level=LEVEL_HIGH)

    assert resolver.resolve("scope-2", {"tool_name": "delete_file", "category": "destructive"}) is None


# --- deterministic resolution --------------------------------------------


def test_resolution_is_deterministic_across_repeated_calls(service, resolver):
    service.create("scope-1", "exact-profile", action_name="delete_file", default_level=LEVEL_CRITICAL)

    first = resolver.resolve("scope-1", {"tool_name": "delete_file"})
    second = resolver.resolve("scope-1", {"tool_name": "delete_file"})
    assert first == second


def test_resolution_is_read_only_and_never_mutates_state(service, resolver):
    profile = service.create("scope-1", "default", default_level=LEVEL_LOW)

    resolver.resolve("scope-1", {"tool_name": "delete_file"})

    unchanged = service.get(profile.profile_id)
    assert unchanged == profile


# --- provenance ----------------------------------------------------------


def test_provenance_embeds_selected_profile_and_action_context(service, resolver):
    profile = service.create(
        "scope-1", "exact-profile", action_name="delete_file",
        action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"}, reason="dangerous")],
    )

    action_context = {"tool_name": "delete_file", "arguments": {"path": "/tmp/x"}}
    result = resolver.resolve("scope-1", action_context)

    assert result.provenance["profile"].profile_id == profile.profile_id
    assert result.provenance["action_context"] == action_context
    assert result.provenance["action_context"] is not action_context
    assert result.provenance["tier"] == TIER_EXACT_ACTION
    assert result.matched_rule_id == "r1"
    assert "dangerous" in result.reason
    assert result.version == profile.version


def test_provenance_names_tier_for_default_fallback(service, resolver):
    service.create("scope-1", "default", default_level=LEVEL_MEDIUM)

    result = resolver.resolve("scope-1", {"tool_name": "anything"})
    assert result.tier == TIER_SCOPE_DEFAULT
    assert "scope default" in result.reason


# --- validation ------------------------------------------------------------


def test_resolve_requires_scope_id(resolver):
    with pytest.raises(InvalidRiskProfileError):
        resolver.resolve("", {"tool_name": "x"})


def test_resolve_rejects_non_dict_action_context(service, resolver):
    service.create("scope-1", "default")
    with pytest.raises(InvalidActionContextError):
        resolver.resolve("scope-1", "not-a-dict")


def test_action_name_must_be_non_blank_string(service):
    with pytest.raises(InvalidRiskProfileError):
        service.create("scope-1", "p1", action_name="")


def test_action_category_must_be_non_blank_string(service):
    with pytest.raises(InvalidRiskProfileError):
        service.create("scope-1", "p1", action_category="   ")


# --- Commit #1 backward compatibility -------------------------------------


def test_service_resolve_still_only_considers_scope_default_tier(service):
    """Commit #1's own LLMAgentRiskProfileService.resolve() must remain
    scope-default-only and unaware of Commit #2's exact/category tiers."""
    service.create("scope-1", "exact-profile", action_name="delete_file", default_level=LEVEL_CRITICAL)

    assert service.resolve("scope-1", {"tool_name": "delete_file"}) is None
