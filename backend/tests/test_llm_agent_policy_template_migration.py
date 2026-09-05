import pytest

from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyService
from backend.agent_policy_template_migration import (
    InvalidMigratedTemplateError,
    LLMAgentPolicyTemplateMigrationRecord,
    LLMAgentPolicyTemplateMigrator,
    MigrationCheck,
    UnknownTemplateMigrationError,
    UnsupportedTemplateMigrationError,
)
from backend.agent_policy_templates import LLMAgentPolicyTemplate, LLMAgentPolicyTemplateService


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
    migrator = LLMAgentPolicyTemplateMigrator(template_service)
    return template_service, migrator


def test_supported_migration_fills_blank_reasons_only():
    template_service, migrator = _services()
    created = template_service.create("standard-access", "d", _definition())

    check = migrator.can_migrate(created, 2)
    assert isinstance(check, MigrationCheck)
    assert check.can_migrate
    assert check.source_version == 1
    assert check.target_version == 2

    migrated = migrator.migrate(created, 2)

    assert isinstance(migrated, LLMAgentPolicyTemplate)
    assert migrated.template_id != created.template_id
    assert migrated.name == created.name
    assert migrated.description == created.description

    rules_by_id = {rule["rule_id"]: rule for rule in migrated.policy_definition["rules"]}
    assert set(rules_by_id) == {"allow-{tool_name}", "deny-delete"}
    # the blank reason was filled in ...
    assert rules_by_id["allow-{tool_name}"]["reason"] != ""
    assert "allow-{tool_name}" in rules_by_id["allow-{tool_name}"]["reason"]
    # ... but an already-present reason, and every other field, is untouched
    assert rules_by_id["deny-delete"]["reason"] == "never allowed"
    assert rules_by_id["allow-{tool_name}"]["effect"] == ALLOW
    assert rules_by_id["allow-{tool_name}"]["match"] == {"tool_name": "{tool_name}"}


def test_identity_migration_for_same_version():
    template_service, migrator = _services()
    created = template_service.create("standard-access", "d", _definition())

    migrated = migrator.migrate(created, 1)

    assert migrated.policy_definition == created.policy_definition


def test_unsupported_transition_out_of_range():
    template_service, migrator = _services()
    created = template_service.create("standard-access", "d", _definition())

    check = migrator.can_migrate(created, 99)
    assert not check.can_migrate
    assert any("not a supported template version" in reason for reason in check.reasons)

    with pytest.raises(UnsupportedTemplateMigrationError):
        migrator.migrate(created, 99)


def test_unsupported_transition_backward():
    template_service, migrator = _services()
    created = template_service.create("standard-access", "d", _definition())
    at_v2 = template_service.update(
        created.template_id, policy_definition=_definition(rules=_definition()["rules"] + [
            {"rule_id": "extra", "effect": ALLOW},
        ]),
    )
    assert at_v2.version == 2

    check = migrator.can_migrate(at_v2, 1)
    assert not check.can_migrate
    assert any("backward" in reason for reason in check.reasons)

    with pytest.raises(UnsupportedTemplateMigrationError):
        migrator.migrate(at_v2, 1)


def test_invalid_source_rejected():
    _, migrator = _services()
    broken = LLMAgentPolicyTemplate(
        name="broken",
        description="d",
        policy_definition={
            "name_template": "x",
            "rules": [{"rule_id": "dup", "effect": ALLOW}, {"rule_id": "dup", "effect": ALLOW}],
        },
    )

    check = migrator.can_migrate(broken, 2)
    assert not check.can_migrate
    assert any("invalid source template" in reason for reason in check.reasons)

    with pytest.raises(UnsupportedTemplateMigrationError):
        migrator.migrate(broken, 2)


def test_invalid_migrated_result_rejected():
    template_service = LLMAgentPolicyTemplateService(LLMAgentPolicyService())

    class _AlwaysIncompatible:
        def check(self, template, target_context):
            class _Result:
                compatible = False
                reasons = ["forced incompatibility for testing"]

            return _Result()

    migrator = LLMAgentPolicyTemplateMigrator(template_service, compatibility=_AlwaysIncompatible())
    created = template_service.create("standard-access", "d", _definition())

    with pytest.raises(InvalidMigratedTemplateError):
        migrator.migrate(created, 2)


def test_source_remains_unchanged():
    template_service, migrator = _services()
    created = template_service.create("standard-access", "d", _definition())
    before = template_service.get(created.template_id)

    migrator.migrate(created, 2)

    after = template_service.get(created.template_id)
    assert after.version == before.version
    assert after.updated_at == before.updated_at
    assert after.policy_definition == before.policy_definition


def test_provenance():
    template_service, migrator = _services()
    created = template_service.create("standard-access", "d", _definition())

    migrated = migrator.migrate(created, 2)
    record = migrator.provenance(migrated.template_id)

    assert isinstance(record, LLMAgentPolicyTemplateMigrationRecord)
    assert record.source_template_id == created.template_id
    assert record.source_version == 1
    assert record.migrated_template_id == migrated.template_id
    assert record.target_version == 2

    with pytest.raises(UnknownTemplateMigrationError):
        migrator.provenance("missing-id")


def test_compatibility_integration_normal_migration_succeeds():
    template_service, migrator = _services()
    created = template_service.create("standard-access", "d", _definition())

    # a normal migration passes Commit #4's own post-migration
    # compatibility gate without needing any special-casing
    migrated = migrator.migrate(created, 2)
    assert migrated is not None


def test_deterministic_migration_content():
    template_service, migrator = _services()
    created = template_service.create("standard-access", "d", _definition())

    first = migrator.migrate(created, 2)
    second = migrator.migrate(created, 2)

    assert first.template_id != second.template_id
    assert first.name == second.name
    assert first.description == second.description
    assert first.policy_definition == second.policy_definition
