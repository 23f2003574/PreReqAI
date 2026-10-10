import pytest

from backend.agent_policy_deployment_history import (
    DEPLOYMENT_FAILED,
    LLMAgentPolicyDeploymentHistory,
    LLMAgentPolicyDeploymentHistoryTrackedDeploymentService,
)
from backend.agent_policy_deployment_rollback import (
    ALREADY_CURRENT,
    ROLLED_BACK,
    LLMAgentPolicyDeploymentRollbackError,
    LLMAgentPolicyDeploymentRollbackService,
)
from backend.agent_policy_deployment_verification import LLMAgentPolicyDeploymentVerifier
from backend.agent_policy_engine import ACTIVE, ALLOW, ARCHIVED, DENY, LLMAgentPolicyService
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
    deployment_history = LLMAgentPolicyDeploymentHistory()
    deployment_service = LLMAgentPolicyDeploymentHistoryTrackedDeploymentService(
        policy_service, template_service, instantiator, history_service=deployment_history,
    )
    verifier = LLMAgentPolicyDeploymentVerifier(policy_service, template_service, instantiator, deployment_history)
    rollback_service = LLMAgentPolicyDeploymentRollbackService(
        policy_service, deployment_service, deployment_history, verifier, template_service, instantiator,
    )
    return {
        "policy_service": policy_service,
        "template_service": template_service,
        "instantiator": instantiator,
        "deployment_history": deployment_history,
        "deployment_service": deployment_service,
        "verifier": verifier,
        "rollback_service": rollback_service,
    }


def _instantiate(env, scope_id="notebook-1", tool_name="lookup", name="standard-access"):
    created = env["template_service"].create(name, "d", _definition())
    policy = env["instantiator"].instantiate(
        created.template_id, scope_id, {"scope_name": "Notebook", "tool_name": tool_name},
    )
    return created, policy


def _deploy_two_versions(env, scope_id="notebook-1"):
    created, policy_a = _instantiate(env, scope_id=scope_id, tool_name="lookup")
    result_a = env["deployment_service"].deploy(policy_a.policy_id, {"scope_id": scope_id})

    policy_b = env["instantiator"].instantiate(
        created.template_id, scope_id, {"scope_name": "Notebook", "tool_name": "search"},
    )
    result_b = env["deployment_service"].deploy(policy_b.policy_id, {"scope_id": scope_id})

    return created, policy_a, result_a, policy_b, result_b


def test_successful_rollback():
    env = _services()
    created, policy_a, result_a, policy_b, result_b = _deploy_two_versions(env)

    rollback_result = env["rollback_service"].rollback(result_a.deployment_id, "reverting bad change", actor="ops")

    assert rollback_result.status == ROLLED_BACK
    assert rollback_result.reason == "reverting bad change"
    assert rollback_result.actor == "ops"
    assert rollback_result.target_deployment_id == result_a.deployment_id
    assert rollback_result.target_policy_id == policy_a.policy_id
    assert rollback_result.source_deployment_id == result_b.deployment_id
    assert rollback_result.source_policy_id == policy_b.policy_id
    assert rollback_result.policy_id not in (policy_a.policy_id, policy_b.policy_id)

    restored = env["policy_service"].get(rollback_result.policy_id)
    assert restored.status == ACTIVE
    assert restored.name == policy_a.name
    assert [r.to_dict() for r in restored.rules] == [r.to_dict() for r in policy_a.rules]

    # neither prior policy is ever reactivated -- policy_a stays archived too
    assert env["policy_service"].get(policy_a.policy_id).status == ARCHIVED
    assert env["policy_service"].get(policy_b.policy_id).status == ARCHIVED

    assert env["deployment_service"].current_for("notebook-1", created.name) == rollback_result.policy_id


def test_invalid_target():
    env = _services()

    with pytest.raises(LLMAgentPolicyDeploymentRollbackError):
        env["rollback_service"].rollback("missing-deployment-id", "reason")


def test_verification_failure_blocks_rollback():
    env = _services()
    created, policy_a, result_a, policy_b, result_b = _deploy_two_versions(env)

    failed_record = env["deployment_history"].record(
        policy_id=policy_a.policy_id, target_scope="notebook-1", status=DEPLOYMENT_FAILED,
        template_id=created.template_id, template_version=created.version,
    )

    with pytest.raises(LLMAgentPolicyDeploymentRollbackError):
        env["rollback_service"].rollback(failed_record.deployment_id, "reason")

    # nothing changed
    assert env["deployment_service"].current_for("notebook-1", created.name) == policy_b.policy_id


def test_activation_failure_leaves_state_unchanged():
    env = _services()
    created, policy_a, result_a, policy_b, result_b = _deploy_two_versions(env)

    # archiving the template itself makes re-instantiation for rollback fail
    env["template_service"].archive(created.template_id)

    with pytest.raises(LLMAgentPolicyDeploymentRollbackError):
        env["rollback_service"].rollback(result_a.deployment_id, "reason")

    assert env["deployment_service"].current_for("notebook-1", created.name) == policy_b.policy_id
    assert env["policy_service"].get(policy_b.policy_id).status == ACTIVE


def test_history_and_provenance():
    env = _services()
    created, policy_a, result_a, policy_b, result_b = _deploy_two_versions(env)

    rollback_result = env["rollback_service"].rollback(result_a.deployment_id, "reverting", actor="ops")

    records = env["deployment_history"].list_for_policy(rollback_result.policy_id)
    assert len(records) == 1
    assert records[0].reason == "reverting"
    assert records[0].actor == "ops"
    assert records[0].template_id == created.template_id

    assert rollback_result.target_template_version == created.version
    assert rollback_result.source_template_version == created.version


def test_idempotent_rollback():
    env = _services()
    created, policy_a, result_a, policy_b, result_b = _deploy_two_versions(env)

    first = env["rollback_service"].rollback(result_a.deployment_id, "reverting")
    assert first.status == ROLLED_BACK

    second = env["rollback_service"].rollback(result_a.deployment_id, "reverting again")
    assert second.status == ALREADY_CURRENT
    assert second.policy_id == first.policy_id

    # no additional policy or deployment record was created
    assert len(env["deployment_history"].list_for_policy(first.policy_id)) == 1


def test_scope_isolation():
    env = _services()
    created_a, policy_a1, result_a1, policy_a2, result_a2 = _deploy_two_versions(env, scope_id="notebook-a")

    created_b = env["template_service"].create("standard-access-b", "d", _definition())
    policy_b1 = env["instantiator"].instantiate(
        created_b.template_id, "notebook-b", {"scope_name": "Notebook", "tool_name": "lookup"},
    )
    result_b1 = env["deployment_service"].deploy(policy_b1.policy_id, {"scope_id": "notebook-b"})

    rollback_result = env["rollback_service"].rollback(result_a1.deployment_id, "reverting scope a")

    assert rollback_result.scope_id == "notebook-a"
    # scope-b's own deployment is completely untouched
    assert env["deployment_service"].current_for("notebook-b", created_b.name) == policy_b1.policy_id
    assert env["policy_service"].get(policy_b1.policy_id).status == ACTIVE


def test_restored_state_verification():
    env = _services()
    created, policy_a, result_a, policy_b, result_b = _deploy_two_versions(env)

    rollback_result = env["rollback_service"].rollback(result_a.deployment_id, "reverting")

    assert rollback_result.verification.verified
    assert rollback_result.verification.policy_id == rollback_result.policy_id
    assert rollback_result.verification.reasons == []
