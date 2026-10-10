import pytest

from backend.agent_policy_engine import ALLOW, DENY, InMemoryLLMAgentPolicyStore, LLMAgentPolicyService
from backend.agent_policy_history import LLMAgentPolicyHistoryService, LLMAgentPolicyHistoryTrackedService
from backend.agent_policy_template_compatibility import LLMAgentPolicyTemplateCompatibility
from backend.agent_policy_template_instantiation_pipeline import (
    LLMAgentPolicyTemplateInstantiator,
    TemplateInstantiationCompatibilityError,
    TemplateInstantiationValidationError,
    UnknownTemplateInstantiationPipelineError,
)
from backend.agent_policy_templates import (
    ArchivedPolicyTemplateError,
    LLMAgentPolicyTemplate,
    LLMAgentPolicyTemplateService,
    UnknownPolicyTemplateError,
)
from backend.agent_policy_versioning import LLMAgentPolicyVersionService


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
    template_service = LLMAgentPolicyTemplateService(LLMAgentPolicyService())
    instantiator = LLMAgentPolicyTemplateInstantiator(template_service)
    return template_service, instantiator


def test_valid_instantiation():
    template_service, instantiator = _services()
    created = template_service.create("standard-access", "d", _definition())

    policy = instantiator.instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"},
    )

    assert policy.scope_id == "notebook-1"
    assert policy.name == "Notebook tool access"
    assert {rule.rule_id for rule in policy.rules} == {"allow-lookup", "deny-delete"}


def test_parameter_substitution_is_deterministic():
    template_service, instantiator = _services()
    created = template_service.create("standard-access", "d", _definition())
    params = {"scope_name": "Notebook", "tool_name": "lookup"}

    first = instantiator.instantiate(created.template_id, "notebook-1", params)
    second = instantiator.instantiate(created.template_id, "notebook-2", params)

    assert first.name == second.name
    assert [r.rule_id for r in first.rules] == [r.rule_id for r in second.rules]
    assert [r.match for r in first.rules] == [r.match for r in second.rules]


def test_validation_failure_blocks_instantiation():
    template_service, instantiator = _services()
    created = template_service.create("standard-access", "d", _definition())

    # missing "tool_name" parameter -> Commit #3's own validator rejects it
    with pytest.raises(TemplateInstantiationValidationError):
        instantiator.instantiate(created.template_id, "notebook-1", {"scope_name": "Notebook"})

    # nothing was persisted or recorded
    assert template_service.list() == [created]
    with pytest.raises(UnknownPolicyTemplateError):
        template_service.get("no-such-policy-would-exist-anyway")


def test_invalid_source_template_blocks_instantiation():
    broken = LLMAgentPolicyTemplate(
        name="broken", description="d",
        policy_definition={"name_template": "x", "rules": [{"rule_id": "dup", "effect": ALLOW}, {"rule_id": "dup", "effect": ALLOW}]},
    )
    template_service = LLMAgentPolicyTemplateService(LLMAgentPolicyService())
    template_service.store.save(broken)
    instantiator = LLMAgentPolicyTemplateInstantiator(template_service)

    with pytest.raises(TemplateInstantiationValidationError):
        instantiator.instantiate(broken.template_id, "notebook-1", {})


def test_compatibility_failure_blocks_instantiation():
    template_service, instantiator = _services()
    created = template_service.create("standard-access", "d", _definition())

    with pytest.raises(TemplateInstantiationCompatibilityError):
        instantiator.instantiate(
            created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"},
            target_context={"supported_effects": {"ALLOW"}},
        )

    # nothing was persisted
    with pytest.raises(UnknownTemplateInstantiationPipelineError):
        instantiator.provenance("any-policy-id")


def test_archived_template_cannot_instantiate():
    template_service, instantiator = _services()
    created = template_service.create("standard-access", "d", _definition())
    template_service.archive(created.template_id)

    with pytest.raises(ArchivedPolicyTemplateError):
        instantiator.instantiate(created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"})


def test_migration_integration():
    template_service, instantiator = _services()
    created = template_service.create("standard-access", "d", _definition())

    policy = instantiator.instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"}, target_version=2,
    )

    record = instantiator.provenance(policy.policy_id)
    assert record.migrated is True
    assert record.requested_template_id == created.template_id
    assert record.resolved_template_id != created.template_id
    assert record.target_version == 2

    # the migrated template is a real, separately discoverable Commit #1 record
    migrated_template = template_service.get(record.resolved_template_id)
    assert migrated_template.version == 1  # Commit #1's own bookkeeping for the new record
    reasons = {rule["rule_id"]: rule["reason"] for rule in migrated_template.policy_definition["rules"]}
    assert reasons["allow-{tool_name}"] != ""  # the blank reason was filled in by the migration

    # the source template itself is completely untouched
    source = template_service.get(created.template_id)
    assert source.version == 1
    assert source.policy_definition == created.policy_definition


def test_persistence_failure_leaves_nothing_partial():
    class _BrokenPolicyService(LLMAgentPolicyService):
        def create(self, *args, **kwargs):
            raise RuntimeError("simulated persistence failure")

    template_service = LLMAgentPolicyTemplateService(_BrokenPolicyService())
    instantiator = LLMAgentPolicyTemplateInstantiator(template_service)
    created = template_service.create("standard-access", "d", _definition())

    with pytest.raises(RuntimeError):
        instantiator.instantiate(created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"})

    # no pipeline provenance was ever recorded for this failed attempt
    with pytest.raises(UnknownTemplateInstantiationPipelineError):
        instantiator.provenance("whatever-policy-id-might-have-been")

    # the template itself is untouched
    after = template_service.get(created.template_id)
    assert after.policy_definition == created.policy_definition
    assert after.version == created.version


def test_provenance():
    template_service, instantiator = _services()
    created = template_service.create("standard-access", "d", _definition())

    policy = instantiator.instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"},
    )

    record = instantiator.provenance(policy.policy_id)
    assert record.requested_template_id == created.template_id
    assert record.resolved_template_id == created.template_id
    assert record.migrated is False
    assert record.target_version is None
    assert record.scope_id == "notebook-1"
    assert record.policy_id == policy.policy_id
    assert record.parameters == {"scope_name": "Notebook", "tool_name": "lookup"}

    with pytest.raises(UnknownTemplateInstantiationPipelineError):
        instantiator.provenance("missing-policy-id")


def test_reuses_existing_policy_versioning():
    store = InMemoryLLMAgentPolicyStore()
    history_service = LLMAgentPolicyHistoryService()
    tracked_policy_service = LLMAgentPolicyHistoryTrackedService(store=store, history_service=history_service)
    bare_policy_service = LLMAgentPolicyService(store=store)
    version_service = LLMAgentPolicyVersionService(bare_policy_service, history_service)

    template_service = LLMAgentPolicyTemplateService(tracked_policy_service)
    instantiator = LLMAgentPolicyTemplateInstantiator(template_service, version_service=version_service)
    created = template_service.create("standard-access", "d", _definition())

    policy = instantiator.instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "lookup"},
    )

    versions = version_service.list_versions(policy.policy_id)
    assert len(versions) == 1
    assert versions[0].version == 1

    record = instantiator.provenance(policy.policy_id)
    assert record.current_version == 1
