import pytest

from backend.agent_policy_engine import ALLOW, LLMAgentPolicyService
from backend.agent_policy_template_validation import LLMAgentPolicyTemplateValidator, ValidationResult
from backend.agent_policy_templates import (
    LLMAgentPolicyTemplate,
    LLMAgentPolicyTemplateService,
    MissingTemplateParameterError,
    UnexpectedTemplateParameterError,
)


def _definition(**overrides):
    definition = {
        "name_template": "{scope_name} tool access",
        "rules": [
            {"rule_id": "allow-{tool_name}", "effect": ALLOW, "match": {"tool_name": "{tool_name}"}, "reason": ""},
        ],
    }
    definition.update(overrides)
    return definition


def _services():
    return LLMAgentPolicyTemplateService(LLMAgentPolicyService()), LLMAgentPolicyTemplateValidator()


def _draft(**overrides):
    fields = {"name": "standard-access", "description": "d", "policy_definition": _definition()}
    fields.update(overrides)
    return LLMAgentPolicyTemplate(**fields)


def test_valid_template():
    _, validator = _services()
    result = validator.validate(_draft())

    assert isinstance(result, ValidationResult)
    assert result.is_valid
    assert result.issues == []


def test_valid_definition_and_parameters():
    template_service, validator = _services()
    created = template_service.create("standard-access", "d", _definition())

    assert validator.validate_definition(created.policy_definition).is_valid
    assert validator.validate_parameters(created, {"scope_name": "Notebook", "tool_name": "lookup"}).is_valid


def test_missing_fields():
    _, validator = _services()

    result = validator.validate(_draft(name=""))
    assert not result.is_valid
    assert {issue.code for issue in result.issues} == {"missing_name"}
    assert result.issues[0].path == "name"

    result = validator.validate(_draft(description=""))
    assert {issue.code for issue in result.issues} == {"missing_description"}

    result = validator.validate_definition({"rules": _definition()["rules"]})
    assert {issue.code for issue in result.issues} == {"missing_name_template"}

    result = validator.validate_definition({"name_template": "x", "rules": []})
    assert {issue.code for issue in result.issues} == {"missing_rules"}

    result = validator.validate_definition("not-a-dict")
    assert {issue.code for issue in result.issues} == {"invalid_definition_type"}


def test_embedded_scope_id_rejected():
    _, validator = _services()
    result = validator.validate_definition(_definition(scope_id="notebook-1"))

    assert not result.is_valid
    assert result.issues[0].code == "embedded_scope_id"
    assert result.issues[0].path == "scope_id"


def test_malformed_rules():
    _, validator = _services()

    result = validator.validate_definition(_definition(rules=[{"rule_id": "r1", "effect": "MAYBE"}]))
    assert result.issues[0].code == "invalid_rule"
    assert result.issues[0].path == "rules[0]"

    result = validator.validate_definition(_definition(rules=["not-a-dict"]))
    assert result.issues[0].code == "invalid_rule_type"

    result = validator.validate_definition(_definition(rules=[{"effect": ALLOW}]))  # missing rule_id
    assert result.issues[0].code == "invalid_rule_shape"

    result = validator.validate_definition(
        _definition(rules=[{"rule_id": "dup", "effect": ALLOW}, {"rule_id": "dup", "effect": ALLOW}])
    )
    assert result.issues[0].code == "duplicate_rule_id"
    assert result.issues[0].path == "rules[1].rule_id"


def test_validate_collects_every_issue_in_one_pass():
    _, validator = _services()
    bad = _draft(
        name="",
        description="",
        policy_definition={"rules": [{"rule_id": "r1", "effect": "MAYBE"}]},
    )

    result = validator.validate(bad)

    codes = {issue.code for issue in result.issues}
    assert codes == {"missing_name", "missing_description", "missing_name_template", "invalid_rule"}
    # nested definition issues are prefixed onto the template-level path
    rule_issue = next(issue for issue in result.issues if issue.code == "invalid_rule")
    assert rule_issue.path == "policy_definition.rules[0]"


def test_missing_parameters():
    template_service, validator = _services()
    created = template_service.create("standard-access", "d", _definition())

    result = validator.validate_parameters(created, {"scope_name": "Notebook"})

    assert not result.is_valid
    assert result.issues[0].code == "missing_parameter"
    assert result.issues[0].path == "parameters.tool_name"


def test_unknown_parameters():
    template_service, validator = _services()
    created = template_service.create("standard-access", "d", _definition())

    result = validator.validate_parameters(
        created, {"scope_name": "Notebook", "tool_name": "lookup", "unused": "x"},
    )

    assert not result.is_valid
    assert result.issues[0].code == "unknown_parameter"
    assert result.issues[0].path == "parameters.unused"


def test_invalid_parameter_values():
    template_service, validator = _services()
    created = template_service.create("standard-access", "d", _definition())

    result = validator.validate_parameters(
        created, {"scope_name": {"nested": "dict"}, "tool_name": None},
    )

    assert not result.is_valid
    codes_by_path = {issue.path: issue.code for issue in result.issues}
    assert codes_by_path["parameters.scope_name"] == "invalid_parameter_value"
    assert codes_by_path["parameters.tool_name"] == "invalid_parameter_value"

    # scalars of every kind are accepted
    assert validator.validate_parameters(created, {"scope_name": "Notebook 1", "tool_name": 42}).is_valid

    result = validator.validate_parameters(created, "not-a-dict")
    assert result.issues[0].code == "invalid_parameters_type"


def test_validator_and_instantiation_integration():
    template_service, validator = _services()
    created = template_service.create("standard-access", "d", _definition())

    good_params = {"scope_name": "Notebook", "tool_name": "lookup"}
    assert validator.validate_parameters(created, good_params).is_valid
    policy = template_service.instantiate(created.template_id, "notebook-1", good_params)
    assert policy.scope_id == "notebook-1"

    missing_params = {"scope_name": "Notebook"}
    result = validator.validate_parameters(created, missing_params)
    assert not result.is_valid
    with pytest.raises(MissingTemplateParameterError):
        template_service.instantiate(created.template_id, "notebook-1", missing_params)

    extra_params = {"scope_name": "Notebook", "tool_name": "lookup", "unused": "x"}
    result = validator.validate_parameters(created, extra_params)
    assert not result.is_valid
    with pytest.raises(UnexpectedTemplateParameterError):
        template_service.instantiate(created.template_id, "notebook-1", extra_params)


def test_validate_never_mutates_or_persists():
    template_service, validator = _services()
    created = template_service.create("standard-access", "d", _definition())
    before = template_service.get(created.template_id)

    validator.validate(created)
    validator.validate_definition(created.policy_definition)
    validator.validate_parameters(created, {"scope_name": "Notebook", "tool_name": "lookup"})

    after = template_service.get(created.template_id)
    assert after.updated_at == before.updated_at
    assert after.version == before.version


def test_validate_rejects_wrong_type():
    _, validator = _services()

    result = validator.validate("not-a-template")
    assert result.issues[0].code == "invalid_template_type"

    result = validator.validate_parameters("not-a-template", {})
    assert result.issues[0].code == "invalid_template_type"
