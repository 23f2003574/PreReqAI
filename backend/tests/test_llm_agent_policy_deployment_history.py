import dataclasses

import pytest

from backend.agent_policy_deployment_history import (
    DEPLOYMENT_FAILED,
    DEPLOYMENT_SUCCEEDED,
    InvalidDeploymentRecordError,
    LLMAgentPolicyDeploymentHistory,
    LLMAgentPolicyDeploymentHistoryTrackedDeploymentService,
    LLMAgentPolicyDeploymentRecord,
    UnknownDeploymentRecordError,
)
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyService
from backend.agent_policy_template_deployment import DeploymentCompatibilityError, InvalidDeploymentPolicyError
from backend.agent_policy_template_instantiation_pipeline import LLMAgentPolicyTemplateInstantiator
from backend.agent_policy_templates import LLMAgentPolicyTemplateService


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
    policy_service = LLMAgentPolicyService()
    template_service = LLMAgentPolicyTemplateService(policy_service)
    instantiator = LLMAgentPolicyTemplateInstantiator(template_service)
    history_service = LLMAgentPolicyDeploymentHistory()
    deployment_service = LLMAgentPolicyDeploymentHistoryTrackedDeploymentService(
        policy_service, template_service, instantiator, history_service=history_service,
    )
    return policy_service, template_service, instantiator, deployment_service, history_service


def _instantiate(template_service, instantiator, scope_id="notebook-1", tool_name="lookup", name="standard-access"):
    created = template_service.create(name, "d", _definition())
    policy = instantiator.instantiate(
        created.template_id, scope_id, {"scope_name": "Notebook", "tool_name": tool_name},
    )
    return created, policy


def test_successful_deployment_record():
    _, template_service, instantiator, deployment_service, history_service = _services()
    created, policy = _instantiate(template_service, instantiator)

    result = deployment_service.deploy(policy.policy_id, {"scope_id": "notebook-1"})

    records = history_service.list_for_policy(policy.policy_id)
    assert len(records) == 1
    record = records[0]
    assert isinstance(record, LLMAgentPolicyDeploymentRecord)
    assert record.deployment_id == result.deployment_id
    assert record.status == DEPLOYMENT_SUCCEEDED
    assert record.policy_id == policy.policy_id
    assert record.target_scope == "notebook-1"
    assert record.template_id == created.template_id
    assert record.template_version == created.version


def test_failed_deployment_record_unknown_policy():
    _, template_service, instantiator, deployment_service, history_service = _services()

    from backend.agent_policy_engine import UnknownAgentPolicyError

    with pytest.raises(UnknownAgentPolicyError):
        deployment_service.deploy("missing-policy-id", {"scope_id": "notebook-1"})

    records = history_service.list_for_policy("missing-policy-id")
    assert len(records) == 1
    assert records[0].status == DEPLOYMENT_FAILED
    assert records[0].template_id is None
    assert "missing-policy-id" in records[0].provenance["reason"]


def test_failed_deployment_record_incompatible():
    _, template_service, instantiator, deployment_service, history_service = _services()
    created, policy = _instantiate(template_service, instantiator)

    with pytest.raises(DeploymentCompatibilityError):
        deployment_service.deploy(
            policy.policy_id, {"scope_id": "notebook-1", "supported_effects": {"ALLOW"}},
        )

    records = history_service.list_for_policy(policy.policy_id)
    assert len(records) == 1
    assert records[0].status == DEPLOYMENT_FAILED
    # template provenance is still resolvable even though the deployment failed
    assert records[0].template_id == created.template_id
    assert records[0].template_version == created.version


def test_history_ordering():
    _, template_service, instantiator, deployment_service, history_service = _services()
    created, first_policy = _instantiate(template_service, instantiator)
    deployment_service.deploy(first_policy.policy_id, {"scope_id": "notebook-1"})

    _, second_policy = _instantiate(template_service, instantiator, tool_name="search")
    deployment_service.deploy(second_policy.policy_id, {"scope_id": "notebook-1"})

    records = history_service.list_for_scope("notebook-1")
    assert [r.policy_id for r in records] == [first_policy.policy_id, second_policy.policy_id]
    timestamps = [r.created_at for r in records]
    assert timestamps == sorted(timestamps)


def test_policy_and_template_provenance():
    _, template_service, instantiator, deployment_service, history_service = _services()
    created, policy = _instantiate(template_service, instantiator)
    deployment_service.deploy(policy.policy_id, {"scope_id": "notebook-1"})

    record = history_service.list_for_policy(policy.policy_id)[0]
    assert record.template_id == created.template_id
    assert record.template_version == created.version
    assert record.provenance["previous_policy_id"] is None


def test_scope_isolation():
    _, template_service, instantiator, deployment_service, history_service = _services()
    created, policy_a = _instantiate(template_service, instantiator, scope_id="notebook-a")
    policy_b = instantiator.instantiate(
        created.template_id, "notebook-b", {"scope_name": "Notebook", "tool_name": "search"},
    )

    deployment_service.deploy(policy_a.policy_id, {"scope_id": "notebook-a"})
    deployment_service.deploy(policy_b.policy_id, {"scope_id": "notebook-b"})

    records_a = history_service.list_for_scope("notebook-a")
    records_b = history_service.list_for_scope("notebook-b")
    assert [r.policy_id for r in records_a] == [policy_a.policy_id]
    assert [r.policy_id for r in records_b] == [policy_b.policy_id]


def test_immutable_records():
    _, template_service, instantiator, deployment_service, history_service = _services()
    created, policy = _instantiate(template_service, instantiator)
    deployment_service.deploy(policy.policy_id, {"scope_id": "notebook-1"})
    record = history_service.list_for_policy(policy.policy_id)[0]

    with pytest.raises(dataclasses.FrozenInstanceError):
        record.status = DEPLOYMENT_FAILED


def test_never_exposes_sensitive_policy_payload():
    _, template_service, instantiator, deployment_service, history_service = _services()
    created, policy = _instantiate(template_service, instantiator)
    result = deployment_service.deploy(policy.policy_id, {"scope_id": "notebook-1"})
    record = history_service.get(result.deployment_id)

    serialized = str(record.to_dict())
    assert "tool_name" not in serialized
    assert "allow-lookup" not in serialized
    assert "match" not in serialized


def test_secret_looking_reason_is_redacted():
    _, _, _, _, history_service = _services()
    record = history_service.record(
        policy_id="p1", target_scope="notebook-1", status=DEPLOYMENT_FAILED,
        provenance={"reason": "api_key: sk-abcdefghijklmnop"},
    )
    assert record.provenance["reason"] == "[REDACTED]"


def test_deployment_integration_recording_never_masks_or_falsifies_outcome():
    _, template_service, instantiator, deployment_service, history_service = _services()
    created, policy = _instantiate(template_service, instantiator)

    class _BrokenHistoryStore:
        def save(self, record):
            raise RuntimeError("simulated recording failure")

        def get(self, deployment_id):
            return None

        def list_for_policy(self, policy_id):
            return []

        def list_for_scope(self, scope_id):
            return []

    deployment_service._history_service = LLMAgentPolicyDeploymentHistory(store=_BrokenHistoryStore())

    # a real success is never turned into a failure just because
    # recording it failed
    result = deployment_service.deploy(policy.policy_id, {"scope_id": "notebook-1"})
    assert result is not None

    _, second_policy = _instantiate(template_service, instantiator, tool_name="search")
    # a real failure is never turned into a false success by a
    # recording failure either -- the ORIGINAL error still propagates
    with pytest.raises(DeploymentCompatibilityError):
        deployment_service.deploy(second_policy.policy_id, {"scope_id": "notebook-1", "supported_effects": {"ALLOW"}})


def test_record_validation():
    _, _, _, _, history_service = _services()

    with pytest.raises(InvalidDeploymentRecordError):
        history_service.record(policy_id="", target_scope="notebook-1", status=DEPLOYMENT_SUCCEEDED)
    with pytest.raises(InvalidDeploymentRecordError):
        history_service.record(policy_id="p1", target_scope="notebook-1", status="not-a-status")
    with pytest.raises(UnknownDeploymentRecordError):
        history_service.get("missing-id")
