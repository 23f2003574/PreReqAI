import pytest

from backend.agent_policy_risk_assessment import LEVEL_CRITICAL, LEVEL_HIGH, LEVEL_LOW, LEVEL_MEDIUM
from backend.agent_risk_profile import (
    LLMAgentRiskProfile,
    LLMAgentRiskProfileService,
    RiskProfileActionRule,
)
from backend.agent_risk_profile_versioning import (
    InvalidRiskProfileVersionError,
    JsonRiskProfileVersionStore,
    LLMAgentRiskProfileVersion,
    LLMAgentRiskProfileVersionService,
    UnknownRiskProfileVersionError,
)


def _rule(rule_id, level, match=None):
    return RiskProfileActionRule(rule_id=rule_id, match=match or {}, level=level)


@pytest.fixture
def profile_service():
    return LLMAgentRiskProfileService()


@pytest.fixture
def version_service(profile_service):
    return LLMAgentRiskProfileVersionService(profile_service)


# --- version creation --------------------------------------------------


def test_create_version_snapshots_freshly_created_profile(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)

    version = version_service.create_version(profile.profile_id)
    assert isinstance(version, LLMAgentRiskProfileVersion)
    assert version.profile_id == profile.profile_id
    assert version.version == 1
    assert version.definition["default_level"] == LEVEL_LOW
    assert version.provenance["before"] is None
    assert version.provenance["after"]["profile_id"] == profile.profile_id


def test_create_version_applies_update_and_bumps_version(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)

    v2 = version_service.create_version(
        profile.profile_id, action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})], actor="alice",
        reason="tighten delete risk",
    )
    assert v2.version == 2
    assert v2.definition["action_rules"][0]["rule_id"] == "r1"
    assert v2.provenance["actor"] == "alice"
    assert v2.provenance["reason"] == "tighten delete risk"
    assert v2.provenance["before"]["version"] == 1


def test_create_version_with_no_meaningful_change_returns_same_version(profile_service, version_service):
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    v1 = version_service.create_version(profile.profile_id)

    # A name-only change never bumps Commit #1's own version counter.
    v1_again = version_service.create_version(profile.profile_id, name="renamed")
    assert v1_again.version == 1
    assert v1_again.version_id == v1.version_id


# --- immutable history ---------------------------------------------------


def test_versions_are_never_rewritten_by_a_later_non_meaningful_change(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1")
    v1 = version_service.create_version(profile.profile_id)
    assert v1.definition["name"] == "p1"

    version_service.create_version(profile.profile_id, name="renamed")

    # v1's own recorded definition must still read the name at the time
    # it was captured -- a later name-only edit (never a version bump)
    # must never silently rewrite it.
    unchanged = version_service.get_version(profile.profile_id, 1)
    assert unchanged.definition["name"] == "p1"
    assert unchanged.version_id == v1.version_id


def test_version_dataclass_is_frozen():
    version = LLMAgentRiskProfileVersion(profile_id="p", version=1, definition={}, provenance={})
    with pytest.raises(Exception):
        version.version = 2


def test_create_version_never_mutates_a_stored_version_object(profile_service, version_service):
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )
    v1 = version_service.create_version(profile.profile_id)
    v1_reference = version_service.get_version(profile.profile_id, 1)

    version_service.create_version(
        profile.profile_id, action_rules=[_rule("r1", LEVEL_CRITICAL, {"tool_name": "delete_file"})]
    )

    still_v1 = version_service.get_version(profile.profile_id, 1)
    assert still_v1 == v1_reference
    assert still_v1.definition["action_rules"][0]["level"] == LEVEL_HIGH


# --- ordering --------------------------------------------------------------


def test_list_versions_returns_oldest_first(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_MEDIUM)
    version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)

    versions = version_service.list_versions(profile.profile_id)
    assert [entry.version for entry in versions] == [1, 2, 3]
    assert [entry.definition["default_level"] for entry in versions] == [LEVEL_LOW, LEVEL_MEDIUM, LEVEL_HIGH]


# --- historical retrieval --------------------------------------------------


def test_get_version_retrieves_a_specific_historical_version(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_CRITICAL)

    v1 = version_service.get_version(profile.profile_id, 1)
    assert v1.definition["default_level"] == LEVEL_LOW

    v2 = version_service.get_version(profile.profile_id, 2)
    assert v2.definition["default_level"] == LEVEL_CRITICAL


def test_get_version_unknown_number_raises(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    with pytest.raises(UnknownRiskProfileVersionError):
        version_service.get_version(profile.profile_id, 99)


def test_get_version_unknown_profile_raises(version_service):
    with pytest.raises(UnknownRiskProfileVersionError):
        version_service.get_version("never-versioned", 1)


# --- version diff ------------------------------------------------------


def test_diff_reports_added_removed_and_changed_action_rules(profile_service, version_service):
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("keep", LEVEL_LOW, {"tool_name": "read"}), _rule("drop", LEVEL_LOW, {"tool_name": "old"})]
    )
    version_service.create_version(profile.profile_id)
    version_service.create_version(
        profile.profile_id,
        action_rules=[
            _rule("keep", LEVEL_HIGH, {"tool_name": "read"}),
            _rule("added", LEVEL_CRITICAL, {"tool_name": "new"}),
        ],
    )

    result = version_service.diff(profile.profile_id, 1, 2)
    assert result["profile_id"] == profile.profile_id
    assert [rule["rule_id"] for rule in result["removed"]] == ["drop"]
    assert [rule["rule_id"] for rule in result["added"]] == ["added"]
    assert result["changed"][0]["rule_id"] == "keep"
    assert result["changed"][0]["before"]["level"] == LEVEL_LOW
    assert result["changed"][0]["after"]["level"] == LEVEL_HIGH


def test_diff_reports_changed_flat_fields(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1", default_level=LEVEL_LOW)
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id, default_level=LEVEL_CRITICAL)

    result = version_service.diff(profile.profile_id, 1, 2)
    assert result["changed_fields"]["default_level"] == {"before": LEVEL_LOW, "after": LEVEL_CRITICAL}
    assert "name" not in result["changed_fields"]


def test_diff_with_no_changes_reports_empty_diff(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)
    version_service.create_version(profile.profile_id)  # no-op, same version

    result = version_service.diff(profile.profile_id, 1, 1)
    assert result == {
        "profile_id": profile.profile_id,
        "version_a": 1,
        "version_b": 1,
        "added": [],
        "removed": [],
        "changed": [],
        "changed_fields": {},
    }


def test_diff_unknown_version_raises(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(profile.profile_id)

    with pytest.raises(UnknownRiskProfileVersionError):
        version_service.diff(profile.profile_id, 1, 5)


# --- update integration ------------------------------------------------


def test_create_version_delegates_mutation_to_commit1_update(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1")
    version_service.create_version(
        profile.profile_id, action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )

    # Commit #1's own service.get() must reflect the exact same change --
    # this is what "current profile behavior remains compatible with
    # existing callers" means: no parallel/duplicated mutation route.
    live_profile = profile_service.get(profile.profile_id)
    assert live_profile.version == 2
    assert live_profile.action_rules[0].rule_id == "r1"


def test_create_version_propagates_commit1_errors_unchanged(profile_service, version_service):
    from backend.agent_risk_profile import ArchivedRiskProfileError

    profile = profile_service.create("scope-1", "p1")
    profile_service.archive(profile.profile_id)

    with pytest.raises(ArchivedRiskProfileError):
        version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)


def test_create_version_propagates_invalid_action_rule_error(profile_service, version_service):
    from backend.agent_risk_profile import InvalidRiskProfileActionRuleError

    profile = profile_service.create("scope-1", "p1")
    with pytest.raises(InvalidRiskProfileActionRuleError):
        version_service.create_version(profile.profile_id, action_rules=[{"rule_id": "r1", "level": "BOGUS"}])


# --- validation/provenance -------------------------------------------------


def test_create_version_rejects_invalid_resulting_profile():
    # Use a custom, minimal profile_service stand-in is unnecessary --
    # instead exercise the validator gate directly by handing the
    # version service a profile_service whose get() returns a
    # hand-corrupted profile, proving validate() actually runs.
    class _StubProfileService:
        def __init__(self, profile):
            self._profile = profile

        def get(self, profile_id):
            return self._profile

        def update(self, *args, **kwargs):
            raise AssertionError("update() should not be called when no fields are given")

    corrupted = LLMAgentRiskProfile(
        scope_id="scope-1", name="p1", default_level="NOT_A_LEVEL", version=1
    )
    version_service = LLMAgentRiskProfileVersionService(_StubProfileService(corrupted))

    with pytest.raises(InvalidRiskProfileVersionError):
        version_service.create_version(corrupted.profile_id)


def test_provenance_preserves_actor_and_reason(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1")
    version = version_service.create_version(
        profile.profile_id, default_level=LEVEL_HIGH, actor="reviewer-1", reason="raise default risk posture"
    )
    assert version.provenance["actor"] == "reviewer-1"
    assert version.provenance["reason"] == "raise default risk posture"


def test_provenance_before_is_none_only_for_the_first_version(profile_service, version_service):
    profile = profile_service.create("scope-1", "p1")
    v1 = version_service.create_version(profile.profile_id)
    assert v1.provenance["before"] is None

    v2 = version_service.create_version(profile.profile_id, default_level=LEVEL_HIGH)
    assert v2.provenance["before"] is not None
    assert v2.provenance["before"]["version"] == 1


# --- persistence backends -------------------------------------------------


def test_json_store_round_trips_across_service_instances(tmp_path):
    path = tmp_path / "risk_profile_versions.json"
    profile_service = LLMAgentRiskProfileService()
    profile = profile_service.create(
        "scope-1", "p1", action_rules=[_rule("r1", LEVEL_HIGH, {"tool_name": "delete_file"})]
    )

    service1 = LLMAgentRiskProfileVersionService(profile_service, store=JsonRiskProfileVersionStore(path))
    service1.create_version(profile.profile_id)

    service2 = LLMAgentRiskProfileVersionService(profile_service, store=JsonRiskProfileVersionStore(path))
    versions = service2.list_versions(profile.profile_id)
    assert len(versions) == 1
    assert versions[0].definition["action_rules"][0]["rule_id"] == "r1"
