import pytest

from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyService
from backend.agent_policy_template_compatibility import CompatibilityResult, LLMAgentPolicyTemplateCompatibility
from backend.agent_policy_templates import LLMAgentPolicyTemplateService


def _definition(**overrides):
    definition = {
        "name_template": "{scope_name} tool access",
        "rules": [
            {"rule_id": "allow-{tool_name}", "effect": ALLOW, "match": {"tool_name": "{tool_name}"}, "reason": ""},
            {"rule_id": "deny-delete", "effect": DENY, "match": {"tool_name": "delete"}, "reason": "never"},
        ],
    }
    definition.update(overrides)
    return definition


def _services():
    template_service = LLMAgentPolicyTemplateService(LLMAgentPolicyService())
    compatibility = LLMAgentPolicyTemplateCompatibility()
    return template_service, compatibility


def _full_target_context(**overrides):
    context = {
        "policy_schema_version": 1,
        "supported_effects": {"ALLOW", "DENY"},
        "supported_match_fields": {"tool_name"},
        "scope_id": "notebook-1",
    }
    context.update(overrides)
    return context


def test_compatible_template():
    template_service, compatibility = _services()
    created = template_service.create("standard-access", "d", _definition())

    result = compatibility.check(created, _full_target_context())

    assert isinstance(result, CompatibilityResult)
    assert result.compatible
    assert result.reasons == []
    assert result.template_id == created.template_id
    assert result.template_version == created.version


def test_schema_version_mismatch():
    template_service, compatibility = _services()
    created = template_service.create("standard-access", "d", _definition())

    result = compatibility.check(created, _full_target_context(policy_schema_version=0))

    assert not result.compatible
    assert any("schema version" in reason for reason in result.reasons)
    assert result.provenance["policy_schema_version"] == 0
    assert result.provenance["min_supported_schema_version"] == 1


def test_compatible_version_upgrade():
    template_service, compatibility = _services()
    created = template_service.create("standard-access", "d", _definition())

    result = compatibility.check(created, _full_target_context(policy_schema_version=5))

    assert result.compatible
    assert result.provenance["policy_schema_version"] == 5


def test_missing_capability():
    template_service, compatibility = _services()
    created = template_service.create("standard-access", "d", _definition())

    result = compatibility.check(created, _full_target_context(supported_effects={"ALLOW"}))

    assert not result.compatible
    assert result.provenance["missing_capabilities"] == ["DENY"]
    assert any("DENY" in reason for reason in result.reasons)


def test_unsupported_rule_feature():
    template_service, compatibility = _services()
    created = template_service.create(
        "standard-access", "d", _definition(
            rules=_definition()["rules"] + [{"rule_id": "risk-gate", "effect": DENY, "match": {"risk_level": "high"}}],
        ),
    )

    result = compatibility.check(created, _full_target_context())

    assert not result.compatible
    assert result.provenance["unsupported_features"] == ["risk_level"]
    assert any("risk_level" in reason for reason in result.reasons)


def test_invalid_target_scope_configuration():
    template_service, compatibility = _services()
    created = template_service.create("standard-access", "d", _definition())

    result = compatibility.check(created, _full_target_context(scope_id=""))

    assert not result.compatible
    assert any("target scope configuration" in reason for reason in result.reasons)


def test_unspecified_capabilities_impose_no_restriction():
    template_service, compatibility = _services()
    created = template_service.create("standard-access", "d", _definition())

    # target_context declares no supported_effects/supported_match_fields at all
    result = compatibility.check(created, {"policy_schema_version": 1, "scope_id": "notebook-1"})

    assert result.compatible


def test_reuses_existing_validation_after_compatibility_succeeds():
    template_service, compatibility = _services()
    # a template whose defintion is already malformed at the Commit #1 level
    # cannot be created via the service, so build a raw dataclass draft instead
    from backend.agent_policy_templates import LLMAgentPolicyTemplate

    draft = LLMAgentPolicyTemplate(
        name="broken",
        description="d",
        # every effect/match field here is one the target already
        # declares support for -- only Commit #3's own rule validation
        # (duplicate rule_id) can catch this one
        policy_definition={
            "name_template": "x",
            "rules": [{"rule_id": "dup", "effect": ALLOW}, {"rule_id": "dup", "effect": ALLOW}],
        },
    )

    result = compatibility.check(draft, _full_target_context())

    assert not result.compatible
    assert any("duplicate_rule_id" in reason for reason in result.reasons)


def test_deterministic_result():
    template_service, compatibility = _services()
    created = template_service.create("standard-access", "d", _definition())
    context = _full_target_context()

    first = compatibility.check(created, context)
    second = compatibility.check(created, context)

    assert first == second


def test_invalid_input_types():
    _, compatibility = _services()

    result = compatibility.check("not-a-template", {})
    assert not result.compatible
    assert result.template_id is None

    template_service, compatibility = _services()
    created = template_service.create("standard-access", "d", _definition())
    result = compatibility.check(created, "not-a-dict")
    assert not result.compatible


def test_instantiation_integration():
    template_service, compatibility = _services()
    created = template_service.create("standard-access", "d", _definition())

    compatible_result = compatibility.check(created, _full_target_context())
    assert compatible_result.compatible
    policy = template_service.instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"},
    )
    assert policy.scope_id == "notebook-1"

    incompatible_result = compatibility.check(created, _full_target_context(supported_effects={"ALLOW"}))
    assert not incompatible_result.compatible
    # a caller that respects the compatibility gate never calls instantiate()
    # for an incompatible result -- Commit #1's own instantiate() has no
    # notion of "capabilities" and would otherwise succeed regardless,
    # which is exactly why this gate must run first
