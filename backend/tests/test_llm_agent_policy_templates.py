import pytest

from backend.agent_policy_engine import ALLOW, DENY, InvalidAgentPolicyError, InvalidPolicyRuleError, LLMAgentPolicy, LLMAgentPolicyService
from backend.agent_policy_templates import (
    ACTIVE,
    ARCHIVED,
    ArchivedPolicyTemplateError,
    InvalidPolicyTemplateDefinitionError,
    InvalidPolicyTemplateError,
    InvalidPolicyTemplateStatusError,
    InvalidTemplateParametersError,
    LLMAgentPolicyTemplate,
    LLMAgentPolicyTemplateService,
    MissingTemplateParameterError,
    UnexpectedTemplateParameterError,
    UnknownPolicyTemplateError,
    UnknownPolicyTemplateInstantiationError,
)


def _definition(**overrides):
    definition = {
        "name_template": "{scope_name} tool access",
        "rules": [
            {"rule_id": "allow-{tool_name}", "effect": ALLOW, "match": {"tool_name": "{tool_name}"}, "reason": ""},
            {"rule_id": "deny-delete", "effect": DENY, "match": {"tool_name": "delete"}, "reason": "never allowed"},
        ],
    }
    definition.update(overrides)
    return definition


def _services():
    return LLMAgentPolicyTemplateService(LLMAgentPolicyService())


def test_create_and_get():
    service = _services()

    created = service.create("standard-access", "Standard tool-access policy", _definition())

    assert isinstance(created, LLMAgentPolicyTemplate)
    assert created.template_id is not None
    assert created.status == ACTIVE
    assert created.version == 1
    assert created.created_at is not None
    assert created.updated_at is not None

    fetched = service.get(created.template_id)
    assert fetched.name == "standard-access"
    assert fetched.policy_definition["name_template"] == "{scope_name} tool access"


def test_missing_template():
    service = _services()

    with pytest.raises(UnknownPolicyTemplateError):
        service.get("missing-id")
    with pytest.raises(UnknownPolicyTemplateError):
        service.update("missing-id", name="new name")
    with pytest.raises(UnknownPolicyTemplateError):
        service.archive("missing-id")
    with pytest.raises(UnknownPolicyTemplateError):
        service.instantiate("missing-id", "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"})


def test_create_validation():
    service = _services()

    with pytest.raises(InvalidPolicyTemplateError):
        service.create("", "description", _definition())
    with pytest.raises(InvalidPolicyTemplateError):
        service.create("name", "", _definition())
    with pytest.raises(InvalidPolicyTemplateDefinitionError):
        service.create("name", "description", "not-a-dict")
    with pytest.raises(InvalidPolicyTemplateDefinitionError):
        service.create("name", "description", {"rules": _definition()["rules"]})  # missing name_template
    with pytest.raises(InvalidPolicyTemplateDefinitionError):
        service.create("name", "description", {"name_template": "x", "rules": []})  # empty rules
    with pytest.raises(InvalidPolicyTemplateDefinitionError):
        service.create("name", "description", _definition(scope_id="notebook-1"))  # embeds a scope_id


def test_definition_reuses_rule_validation():
    service = _services()

    with pytest.raises(InvalidPolicyRuleError):
        service.create(
            "name", "description", _definition(rules=[{"rule_id": "r1", "effect": "MAYBE", "match": {}}]),
        )
    with pytest.raises(InvalidPolicyTemplateDefinitionError):
        service.create(
            "name",
            "description",
            _definition(rules=[{"rule_id": "dup", "effect": ALLOW}, {"rule_id": "dup", "effect": DENY}]),
        )


def test_list_filters_by_status():
    service = _services()
    active = service.create("active-template", "d", _definition())
    to_archive = service.create("archived-template", "d", _definition())
    service.archive(to_archive.template_id)

    assert {t.template_id for t in service.list()} == {active.template_id, to_archive.template_id}
    assert [t.template_id for t in service.list(ACTIVE)] == [active.template_id]
    assert [t.template_id for t in service.list(ARCHIVED)] == [to_archive.template_id]
    with pytest.raises(InvalidPolicyTemplateStatusError):
        service.list("not-a-status")


def test_version_handling():
    service = _services()
    created = service.create("standard-access", "d", _definition())
    assert created.version == 1

    # name/description-only edits never bump version
    renamed = service.update(created.template_id, name="renamed")
    assert renamed.version == 1

    # a genuine definition change bumps version
    changed_definition = _definition(rules=_definition()["rules"] + [{"rule_id": "extra", "effect": ALLOW}])
    updated = service.update(created.template_id, policy_definition=changed_definition)
    assert updated.version == 2

    # re-saving the identical definition does not bump version again
    unchanged = service.update(created.template_id, policy_definition=changed_definition)
    assert unchanged.version == 2


def test_archived_template_rejects_update_and_instantiate():
    service = _services()
    created = service.create("standard-access", "d", _definition())
    service.archive(created.template_id)

    with pytest.raises(ArchivedPolicyTemplateError):
        service.update(created.template_id, name="new name")
    with pytest.raises(ArchivedPolicyTemplateError):
        service.instantiate(created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"})

    # archiving is idempotent
    assert service.archive(created.template_id).status == ARCHIVED


def test_instantiation_produces_normal_policy():
    service = _services()
    created = service.create("standard-access", "d", _definition())

    policy = service.instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook One", "tool_name": "lookup"},
    )

    assert isinstance(policy, LLMAgentPolicy)
    assert policy.scope_id == "notebook-1"
    assert policy.name == "Notebook One tool access"
    assert {rule.rule_id for rule in policy.rules} == {"allow-lookup", "deny-delete"}
    assert policy.rules[0].match == {"tool_name": "lookup"}

    # it is a completely ordinary policy, reachable through Commit #1's
    # own service just like any hand-created one
    fetched = service._policy_service.get(policy.policy_id)
    assert fetched.policy_id == policy.policy_id


def test_parameter_validation():
    service = _services()
    created = service.create("standard-access", "d", _definition())

    with pytest.raises(InvalidTemplateParametersError):
        service.instantiate(created.template_id, "notebook-1", parameters="not-a-dict")
    with pytest.raises(MissingTemplateParameterError):
        service.instantiate(created.template_id, "notebook-1", {"scope_name": "Notebook"})  # missing tool_name
    with pytest.raises(UnexpectedTemplateParameterError):
        service.instantiate(
            created.template_id,
            "notebook-1",
            {"scope_name": "Notebook", "tool_name": "lookup", "unused": "x"},
        )


def test_instantiate_propagates_policy_validation_errors():
    service = _services()
    created = service.create("standard-access", "d", _definition())

    with pytest.raises(InvalidAgentPolicyError):
        service.instantiate(created.template_id, "", {"scope_name": "Notebook", "tool_name": "lookup"})


def test_provenance_and_scope_isolation():
    service = _services()
    created = service.create("standard-access", "d", _definition())

    policy_a = service.instantiate(
        created.template_id, "notebook-a", {"scope_name": "Notebook A", "tool_name": "lookup"},
    )
    policy_b = service.instantiate(
        created.template_id, "notebook-b", {"scope_name": "Notebook B", "tool_name": "search"},
    )

    provenance_a = service.provenance(policy_a.policy_id)
    provenance_b = service.provenance(policy_b.policy_id)

    assert provenance_a.template_id == created.template_id
    assert provenance_a.template_version == created.version
    assert provenance_a.scope_id == "notebook-a"
    assert provenance_a.policy_id == policy_a.policy_id
    assert provenance_a.parameters == {"scope_name": "Notebook A", "tool_name": "lookup"}

    # each instantiation's provenance stays isolated to its own scope/policy
    assert provenance_b.scope_id == "notebook-b"
    assert provenance_b.policy_id != provenance_a.policy_id

    instantiations = service.list_instantiations(created.template_id)
    assert {record.policy_id for record in instantiations} == {policy_a.policy_id, policy_b.policy_id}

    with pytest.raises(UnknownPolicyTemplateInstantiationError):
        service.provenance("missing-policy-id")


def test_provenance_reflects_template_version_at_instantiation_time():
    service = _services()
    created = service.create("standard-access", "d", _definition())

    policy_v1 = service.instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"},
    )

    changed_definition = _definition(rules=_definition()["rules"] + [{"rule_id": "extra", "effect": ALLOW}])
    service.update(created.template_id, policy_definition=changed_definition)

    policy_v2 = service.instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "search"},
    )

    assert service.provenance(policy_v1.policy_id).template_version == 1
    assert service.provenance(policy_v2.policy_id).template_version == 2
