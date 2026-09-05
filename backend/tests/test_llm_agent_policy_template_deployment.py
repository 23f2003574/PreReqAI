import pytest

from backend.agent_policy_engine import ACTIVE, ALLOW, ARCHIVED, DENY, LLMAgentPolicyService
from backend.agent_policy_template_deployment import (
    ALREADY_DEPLOYED,
    DEPLOYED,
    DeploymentCompatibilityError,
    InvalidDeploymentPolicyError,
    LLMAgentPolicyTemplateDeploymentService,
    UnknownDeploymentError,
)
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
    deployment_service = LLMAgentPolicyTemplateDeploymentService(policy_service, template_service, instantiator)
    return policy_service, template_service, instantiator, deployment_service


def _instantiate(template_service, instantiator, scope_id="notebook-1", tool_name="lookup", name="standard-access"):
    created = template_service.create(name, "d", _definition())
    policy = instantiator.instantiate(
        created.template_id, scope_id, {"scope_name": "Notebook", "tool_name": tool_name},
    )
    return created, policy


def test_successful_deployment():
    policy_service, template_service, instantiator, deployment_service = _services()
    created, policy = _instantiate(template_service, instantiator)

    result = deployment_service.deploy(policy.policy_id, {"scope_id": "notebook-1"})

    assert result.status == DEPLOYED
    assert result.policy_id == policy.policy_id
    assert result.scope_id == "notebook-1"
    assert result.template_id == created.template_id
    assert result.template_version == created.version
    assert result.previous_policy_id is None

    assert deployment_service.current_for("notebook-1", "standard-access") == policy.policy_id


def test_validation_failure_unknown_and_archived_policy():
    policy_service, template_service, instantiator, deployment_service = _services()

    from backend.agent_policy_engine import UnknownAgentPolicyError

    with pytest.raises(UnknownAgentPolicyError):
        deployment_service.deploy("missing-policy-id", {"scope_id": "notebook-1"})

    created, policy = _instantiate(template_service, instantiator)
    policy_service.archive(policy.policy_id)

    with pytest.raises(InvalidDeploymentPolicyError):
        deployment_service.deploy(policy.policy_id, {"scope_id": "notebook-1"})


def test_validation_failure_missing_provenance():
    policy_service, template_service, instantiator, deployment_service = _services()
    # a policy created directly, bypassing the Commit #6 pipeline entirely
    raw_policy = policy_service.create("notebook-1", "manual-policy", [])

    with pytest.raises(InvalidDeploymentPolicyError):
        deployment_service.deploy(raw_policy.policy_id, {"scope_id": "notebook-1"})


def test_compatibility_failure_blocks_deployment():
    policy_service, template_service, instantiator, deployment_service = _services()
    created, policy = _instantiate(template_service, instantiator)

    with pytest.raises(DeploymentCompatibilityError):
        deployment_service.deploy(
            policy.policy_id, {"scope_id": "notebook-1", "supported_effects": {"ALLOW"}},
        )

    # nothing was recorded
    with pytest.raises(UnknownDeploymentError):
        deployment_service.provenance(policy.policy_id)
    assert deployment_service.current_for("notebook-1", "standard-access") is None


def test_activation_failure_rollback_leaves_previous_policy_active():
    policy_service, template_service, instantiator, deployment_service = _services()
    created, first_policy = _instantiate(template_service, instantiator)
    deployment_service.deploy(first_policy.policy_id, {"scope_id": "notebook-1"})

    _, second_policy = _instantiate(template_service, instantiator, tool_name="search")

    class _BrokenArchivePolicyService(LLMAgentPolicyService):
        def archive(self, policy_id):
            if policy_id == first_policy.policy_id:
                raise RuntimeError("simulated activation failure")
            return super().archive(policy_id)

    # swap in a policy_service whose archive() fails, on the SAME
    # deployment_service instance that already knows first_policy is
    # the current one for (notebook-1, standard-access) -- a fresh
    # instance would have no memory of that prior deployment at all
    deployment_service._policy_service = _BrokenArchivePolicyService(store=policy_service.store)

    with pytest.raises(RuntimeError):
        deployment_service.deploy(second_policy.policy_id, {"scope_id": "notebook-1"})

    # the previously active policy is untouched
    assert policy_service.get(first_policy.policy_id).status == ACTIVE
    # this failed attempt was never recorded, and the pointer never moved
    with pytest.raises(UnknownDeploymentError):
        deployment_service.provenance(second_policy.policy_id)
    assert deployment_service.current_for("notebook-1", "standard-access") == first_policy.policy_id


def test_previous_policy_preserved_until_new_one_activates():
    policy_service, template_service, instantiator, deployment_service = _services()
    created, first_policy = _instantiate(template_service, instantiator)
    deployment_service.deploy(first_policy.policy_id, {"scope_id": "notebook-1"})
    assert policy_service.get(first_policy.policy_id).status == ACTIVE

    _, second_policy = _instantiate(template_service, instantiator, tool_name="search")
    result = deployment_service.deploy(second_policy.policy_id, {"scope_id": "notebook-1"})

    assert result.previous_policy_id == first_policy.policy_id
    assert policy_service.get(first_policy.policy_id).status == ARCHIVED
    assert policy_service.get(second_policy.policy_id).status == ACTIVE
    assert deployment_service.current_for("notebook-1", "standard-access") == second_policy.policy_id


def test_duplicate_deployment_is_idempotent():
    policy_service, template_service, instantiator, deployment_service = _services()
    created, policy = _instantiate(template_service, instantiator)

    first = deployment_service.deploy(policy.policy_id, {"scope_id": "notebook-1"})
    second = deployment_service.deploy(policy.policy_id, {"scope_id": "notebook-1"})

    assert first.status == DEPLOYED
    assert second.status == ALREADY_DEPLOYED
    assert second.deployment_id == first.deployment_id
    assert second.deployed_at == first.deployed_at
    assert policy_service.get(policy.policy_id).status == ACTIVE

    # provenance always reflects the canonical, still-deployed fact
    assert deployment_service.provenance(policy.policy_id).status == DEPLOYED


def test_provenance():
    policy_service, template_service, instantiator, deployment_service = _services()
    created, policy = _instantiate(template_service, instantiator)

    deployment_service.deploy(policy.policy_id, {"scope_id": "notebook-1"})
    record = deployment_service.provenance(policy.policy_id)

    assert record.policy_id == policy.policy_id
    assert record.template_id == created.template_id
    assert record.template_version == created.version

    with pytest.raises(UnknownDeploymentError):
        deployment_service.provenance("missing-policy-id")


def test_scope_isolation():
    policy_service, template_service, instantiator, deployment_service = _services()
    created, policy_a = _instantiate(template_service, instantiator, scope_id="notebook-a")
    policy_b = instantiator.instantiate(
        created.template_id, "notebook-b", {"scope_name": "Notebook", "tool_name": "search"},
    )

    result_a = deployment_service.deploy(policy_a.policy_id, {"scope_id": "notebook-a"})
    result_b = deployment_service.deploy(policy_b.policy_id, {"scope_id": "notebook-b"})

    assert result_a.previous_policy_id is None
    assert result_b.previous_policy_id is None
    assert deployment_service.current_for("notebook-a", "standard-access") == policy_a.policy_id
    assert deployment_service.current_for("notebook-b", "standard-access") == policy_b.policy_id

    # policy_a is completely unaffected by deploying to notebook-b
    assert policy_service.get(policy_a.policy_id).status == ACTIVE
