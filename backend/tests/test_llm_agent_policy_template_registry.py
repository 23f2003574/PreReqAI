import pytest

from backend.agent_policy_engine import ALLOW, LLMAgentPolicyService
from backend.agent_policy_template_registry import (
    DuplicatePolicyTemplateVersionError,
    InvalidPolicyTemplateFilterError,
    InvalidPolicyTemplateRegistrationError,
    LLMAgentPolicyTemplateRegistry,
)
from backend.agent_policy_templates import (
    ACTIVE,
    ARCHIVED,
    LLMAgentPolicyTemplate,
    LLMAgentPolicyTemplateService,
    UnknownPolicyTemplateError,
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
    template_service = LLMAgentPolicyTemplateService(LLMAgentPolicyService())
    registry = LLMAgentPolicyTemplateRegistry(template_service)
    return template_service, registry


def test_registration_and_get():
    template_service, registry = _services()
    created = template_service.create("standard-access", "d", _definition())

    registered = registry.register(created)

    assert isinstance(registered, LLMAgentPolicyTemplate)
    assert registered.template_id == created.template_id

    fetched = registry.get(created.template_id)
    assert fetched.template_id == created.template_id
    assert fetched.name == "standard-access"


def test_register_rejects_invalid_input():
    _, registry = _services()

    with pytest.raises(InvalidPolicyTemplateRegistrationError):
        registry.register("not-a-template")


def test_register_rejects_unknown_template():
    template_service, registry = _services()
    real = template_service.create("standard-access", "d", _definition())
    # a template-shaped object whose id was never actually created
    forged = LLMAgentPolicyTemplate(
        name=real.name, description=real.description, policy_definition=real.policy_definition,
    )

    with pytest.raises(UnknownPolicyTemplateError):
        registry.register(forged)


def test_duplicate_registration_rejected():
    template_service, registry = _services()
    created = template_service.create("standard-access", "d", _definition())
    registry.register(created)

    # re-registering the exact same template a second time collides on
    # its own unchanged (name, version)
    with pytest.raises(DuplicatePolicyTemplateVersionError):
        registry.register(created)

    # a second, independent template that happens to also start at
    # version 1 under the same name collides too
    other = template_service.create("standard-access", "d", _definition())
    with pytest.raises(DuplicatePolicyTemplateVersionError):
        registry.register(other)


def test_unregister():
    template_service, registry = _services()
    created = template_service.create("standard-access", "d", _definition())
    registry.register(created)

    registry.unregister(created.template_id)

    with pytest.raises(UnknownPolicyTemplateError):
        registry.get(created.template_id)
    with pytest.raises(UnknownPolicyTemplateError):
        registry.resolve("standard-access")

    # the underlying Commit #1 record is completely untouched
    assert template_service.get(created.template_id).status == ACTIVE

    with pytest.raises(UnknownPolicyTemplateError):
        registry.unregister(created.template_id)


def _register_two_versions(template_service, registry, name="standard-access"):
    v1 = template_service.create(name, "d", _definition())
    registry.register(v1)

    v2_created = template_service.create(name, "d", _definition())
    v2 = template_service.update(
        v2_created.template_id, policy_definition=_definition(rules=_definition()["rules"] + [
            {"rule_id": "extra", "effect": ALLOW},
        ]),
    )
    registry.register(v2)
    return v1, v2


def test_version_resolution():
    template_service, registry = _services()
    v1, v2 = _register_two_versions(template_service, registry)

    assert registry.resolve("standard-access", version=1).template_id == v1.template_id
    assert registry.resolve("standard-access", version=2).template_id == v2.template_id

    # no version given resolves to the highest-numbered ACTIVE version
    assert registry.resolve("standard-access").template_id == v2.template_id

    with pytest.raises(UnknownPolicyTemplateError):
        registry.resolve("standard-access", version=99)
    with pytest.raises(UnknownPolicyTemplateError):
        registry.resolve("no-such-template")


def test_missing_template():
    _, registry = _services()

    with pytest.raises(UnknownPolicyTemplateError):
        registry.get("missing-id")
    with pytest.raises(UnknownPolicyTemplateError):
        registry.resolve("missing-name")


def test_status_filtering_and_archive_behavior():
    template_service, registry = _services()
    v1, v2 = _register_two_versions(template_service, registry)
    template_service.archive(v1.template_id)

    # archived templates remain fully discoverable via list()/get() ...
    assert registry.get(v1.template_id).status == ARCHIVED
    all_templates = registry.list()
    assert {t.template_id for t in all_templates} == {v1.template_id, v2.template_id}

    active_only = registry.list({"status": ACTIVE})
    assert [t.template_id for t in active_only] == [v2.template_id]
    archived_only = registry.list({"status": ARCHIVED})
    assert [t.template_id for t in archived_only] == [v1.template_id]

    # ... but resolve() without an explicit version skips archived versions
    template_service.archive(v2.template_id)
    with pytest.raises(UnknownPolicyTemplateError):
        registry.resolve("standard-access")

    # an explicit version request still resolves an archived version
    assert registry.resolve("standard-access", version=1).template_id == v1.template_id

    with pytest.raises(InvalidPolicyTemplateFilterError):
        registry.list({"status": "not-a-status"})


def test_list_filters_by_name():
    template_service, registry = _services()
    a = template_service.create("template-a", "d", _definition())
    b = template_service.create("template-b", "d", _definition())
    registry.register(a)
    registry.register(b)

    assert [t.template_id for t in registry.list({"name": "template-a"})] == [a.template_id]
    assert {t.template_id for t in registry.list()} == {a.template_id, b.template_id}


def test_no_mutation_through_lookup_or_resolve():
    template_service, registry = _services()
    created = template_service.create("standard-access", "d", _definition())
    registry.register(created)
    before = template_service.get(created.template_id)

    registry.get(created.template_id)
    registry.list()
    registry.resolve("standard-access")
    registry.resolve("standard-access", version=1)

    after = template_service.get(created.template_id)
    assert after.updated_at == before.updated_at
    assert after.version == before.version


def test_scope_isolation_through_resolved_template():
    template_service, registry = _services()
    created = template_service.create("standard-access", "d", _definition())
    registry.register(created)

    resolved = registry.resolve("standard-access")
    policy_a = template_service.instantiate(
        resolved.template_id, "notebook-a", {"scope_name": "Notebook A", "tool_name": "lookup"},
    )
    policy_b = template_service.instantiate(
        resolved.template_id, "notebook-b", {"scope_name": "Notebook B", "tool_name": "search"},
    )

    assert policy_a.scope_id == "notebook-a"
    assert policy_b.scope_id == "notebook-b"
    assert template_service.provenance(policy_a.policy_id).scope_id == "notebook-a"
    assert template_service.provenance(policy_b.policy_id).scope_id == "notebook-b"

    # the registry itself never carries or requires any scope_id
    assert registry.get(resolved.template_id).template_id == resolved.template_id
