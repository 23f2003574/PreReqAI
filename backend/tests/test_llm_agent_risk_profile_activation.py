import pytest

from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW
from backend.agent_risk_profile import (
    LLMAgentRiskProfileService,
    RiskProfileActionRule,
    UnknownRiskProfileError,
)
from backend.agent_risk_profile_activation import (
    ACTIVATED,
    ALREADY_ACTIVE,
    ActivationResult,
    ArchivedRiskProfileCannotActivateError,
    IncompatibleRiskProfileVersionError,
    LLMAgentRiskProfileActivationService,
    RiskProfileScopeMismatchError,
)
from backend.agent_risk_profile_versioning import LLMAgentRiskProfileVersionService, UnknownRiskProfileVersionError


def _rule(rule_id, level, match=None):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level)


def _services():
    profile_service = LLMAgentRiskProfileService()
    version_service = LLMAgentRiskProfileVersionService(profile_service)
    activation_service = LLMAgentRiskProfileActivationService(profile_service, version_service)
    return profile_service, version_service, activation_service


# --- activation --------------------------------------------------------


def test_activate_applies_target_version_and_returns_result():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1: no action_rules, LEVEL_LOW
    version_service.create_version(
        profile.profile_id, action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )  # v2, live

    # Restore v1's content while v2 is live -- a real, meaningful
    # activation (v2 was never the target).
    result = activation_service.activate(profile.profile_id, 1, "scope-1")

    assert isinstance(result, ActivationResult)
    assert result.status == ACTIVATED
    assert result.requested_version == 1
    assert result.version == 3
    assert result.previous_version == 2

    live = profile_service.get(profile.profile_id)
    assert live.action_rules == []
    assert live.default_level == LEVEL_LOW


def test_activate_idempotent_when_already_current():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    result = activation_service.activate(profile.profile_id, 1, "scope-1")
    assert result.status == ALREADY_ACTIVE
    assert result.version == 1
    assert result.previous_version == 1


def test_activate_makes_it_the_one_used_by_resolution():
    from backend.agent_risk_profile_resolution import LLMAgentRiskProfileResolver

    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(
        profile.profile_id, action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})]
    )
    activation_service.activate(profile.profile_id, 2, "scope-1")

    resolver = LLMAgentRiskProfileResolver(profile_service)
    resolved = resolver.resolve("scope-1", {"tool_name": "delete_file"})
    assert resolved.level == LEVEL_CRITICAL


# --- deactivation --------------------------------------------------------


def test_deactivate_archives_the_profile():
    from backend.agent_risk_profile import ARCHIVED

    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    archived = activation_service.deactivate(profile.profile_id, "scope-1")
    assert archived.status == ARCHIVED
    assert profile_service.get(profile.profile_id).status == ARCHIVED


def test_deactivate_removes_it_from_resolution():
    from backend.agent_risk_profile_resolution import LLMAgentRiskProfileResolver

    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_HIGH)
    version_service.create_version(profile.profile_id)

    activation_service.deactivate(profile.profile_id, "scope-1")

    resolver = LLMAgentRiskProfileResolver(profile_service)
    assert resolver.resolve("scope-1", {"tool_name": "anything"}) is None


def test_deactivate_scope_mismatch_raises():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1")

    with pytest.raises(RiskProfileScopeMismatchError):
        activation_service.deactivate(profile.profile_id, "scope-2")


def test_deactivate_unknown_profile_raises():
    _, _, activation_service = _services()
    with pytest.raises(UnknownRiskProfileError):
        activation_service.deactivate("does-not-exist", "scope-1")


# --- invalid/incompatible version ------------------------------------------


def test_activate_unknown_version_raises():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    with pytest.raises(UnknownRiskProfileVersionError):
        activation_service.activate(profile.profile_id, 99, "scope-1")


def test_activate_incompatible_version_raises():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"subject": "prod"})]
    )
    version_service.create_version(profile.profile_id)

    with pytest.raises(IncompatibleRiskProfileVersionError):
        activation_service.activate(
            profile.profile_id, 1, "scope-1", target_context={"supported_match_fields": {"tool_name"}}
        )


# --- archived profile -------------------------------------------------


def test_activate_archived_profile_raises():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    profile_service.archive(profile.profile_id)

    with pytest.raises(ArchivedRiskProfileCannotActivateError):
        activation_service.activate(profile.profile_id, 1, "scope-1")


# --- replacement of active version ------------------------------------


def test_activating_older_version_restores_content_as_a_new_version():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1: LEVEL_LOW
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)  # v2: LEVEL_HIGH
    version_service.create_version(profile.profile_id, default_level=LEVEL_CRITICAL)  # v3: LEVEL_CRITICAL

    # "Activating" v1 while live is at v3 never rewrites v1's own
    # immutable definition -- it mints a brand new v4 carrying v1's
    # content forward.
    result = activation_service.activate(profile.profile_id, 1, "scope-1")
    assert result.requested_version == 1
    assert result.version == 4
    assert result.previous_version == 3

    live = profile_service.get(profile.profile_id)
    assert live.default_level == LEVEL_LOW
    assert live.version == 4

    v1_untouched = version_service.get_version(profile.profile_id, 1)
    assert v1_untouched.definition["default_level"] == LEVEL_LOW


def test_replacing_active_version_twice():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1 LOW
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)  # v2 HIGH, live

    first = activation_service.activate(profile.profile_id, 1, "scope-1")  # restore v1 -> mints v3 LOW
    assert first.version == 3
    second = activation_service.activate(profile.profile_id, 2, "scope-1")  # restore v2 -> mints v4 HIGH

    assert second.status == ACTIVATED
    assert second.version == 4
    live = profile_service.get(profile.profile_id)
    assert live.default_level == LEVEL_HIGH


# --- failed activation preserves previous state -----------------------


def test_failed_activation_preserves_previous_state():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    version_service.create_version(profile.profile_id)
    version_service.create_version(
        profile.profile_id, action_rules=[_rule("r2", LEVEL_HIGH, {"subject": "prod"})]
    )
    activation_service.activate(profile.profile_id, 1, "scope-1")

    before = profile_service.get(profile.profile_id)
    assert before.version == 3  # restoring v1 while v2 was live minted a fresh v3
    assert before.action_rules[0].rule_id == "r1"

    with pytest.raises(IncompatibleRiskProfileVersionError):
        activation_service.activate(
            profile.profile_id, 2, "scope-1", target_context={"supported_match_fields": {"tool_name"}}
        )

    after = profile_service.get(profile.profile_id)
    assert after == before
    assert after.action_rules[0].rule_id == "r1"


# --- scope isolation --------------------------------------------------


def test_activate_scope_mismatch_raises():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    with pytest.raises(RiskProfileScopeMismatchError):
        activation_service.activate(profile.profile_id, 1, "scope-2")


def test_get_active_is_scope_isolated():
    profile_service, version_service, activation_service = _services()
    p1 = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(p1.profile_id)
    p2 = profile_service.create("scope-2", "p2", default_level=LEVEL_CRITICAL)
    version_service.create_version(p2.profile_id)

    result1 = activation_service.get_active("scope-1")
    result2 = activation_service.get_active("scope-2")

    assert result1[0].profile_id == p1.profile_id
    assert result2[0].profile_id == p2.profile_id
    assert result1[1].definition["default_level"] == LEVEL_LOW
    assert result2[1].definition["default_level"] == LEVEL_CRITICAL


def test_get_active_returns_none_for_unconfigured_scope():
    _, _, activation_service = _services()
    assert activation_service.get_active("never-configured-scope") is None


def test_get_active_reflects_latest_activation():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)  # v1 LOW
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)  # v2 HIGH, live
    activation_service.activate(profile.profile_id, 1, "scope-1")  # restore v1 -> mints v3 LOW

    profile_result, version_result = activation_service.get_active("scope-1")
    assert profile_result.default_level == LEVEL_LOW
    assert version_result.version == 3


# --- provenance ----------------------------------------------------------


def test_activation_provenance_embeds_versions_and_compatibility():
    profile_service, version_service, activation_service = _services()
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)

    result = activation_service.activate(
        profile.profile_id, 2, "scope-1", actor="reviewer-1", reason="promote high-risk posture"
    )

    assert result.provenance["requested_version"]["version"] == 2
    assert result.provenance["resulting_version"]["version"] == 2
    assert result.provenance["compatibility"]["compatible"] is True
    assert result.provenance["actor"] == "reviewer-1"
    assert result.provenance["reason"] == "promote high-risk posture"


def test_activation_result_immutable():
    result = ActivationResult(
        profile_id="p", scope_id="s", requested_version=1, version=1, previous_version=1,
        status=ACTIVATED, provenance={},
    )
    with pytest.raises(Exception):
        result.version = 2
