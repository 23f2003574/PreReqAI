import pytest

from backend.agent_policy_deployment_governance import KEEP, LLMAgentPolicyDeploymentGovernance
from backend.agent_policy_deployment_health import HEALTHY, LLMAgentPolicyDeploymentHealth
from backend.agent_policy_deployment_history import (
    LLMAgentPolicyDeploymentHistory,
    LLMAgentPolicyDeploymentHistoryTrackedDeploymentService,
)
from backend.agent_policy_deployment_orchestration import (
    DEGRADED,
    ROLLBACK_FAILED,
    ROLLBACK_RECOMMENDED,
    ROLLED_BACK,
    SUCCEEDED,
    VERIFICATION_FAILED,
    LLMAgentPolicyDeploymentOrchestrator,
)
from backend.agent_policy_deployment_rollback import LLMAgentPolicyDeploymentRollbackService
from backend.agent_policy_deployment_verification import LLMAgentPolicyDeploymentVerifier
from backend.agent_policy_engine import ACTIVE, ALLOW, ARCHIVED, DENY, LLMAgentPolicyRule, LLMAgentPolicyService
from backend.agent_policy_template_deployment import DeploymentCompatibilityError
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


def _services(rollback_authorization=None, with_rollback=False):
    policy_service = LLMAgentPolicyService()
    template_service = LLMAgentPolicyTemplateService(policy_service)
    instantiator = LLMAgentPolicyTemplateInstantiator(template_service)
    deployment_history = LLMAgentPolicyDeploymentHistory()
    deployment_service = LLMAgentPolicyDeploymentHistoryTrackedDeploymentService(
        policy_service, template_service, instantiator, history_service=deployment_history,
    )
    verifier = LLMAgentPolicyDeploymentVerifier(policy_service, template_service, instantiator, deployment_history)
    health_service = LLMAgentPolicyDeploymentHealth(deployment_service, deployment_history, verifier, template_service)
    governance_service = LLMAgentPolicyDeploymentGovernance(deployment_history, verifier, health_service)

    rollback_service = None
    if with_rollback or rollback_authorization is not None:
        rollback_service = LLMAgentPolicyDeploymentRollbackService(
            policy_service, deployment_service, deployment_history, verifier, template_service, instantiator,
        )

    orchestrator = LLMAgentPolicyDeploymentOrchestrator(
        deployment_service, deployment_history, verifier, health_service, governance_service,
        rollback_service=rollback_service, rollback_authorization=rollback_authorization,
    )
    return {
        "policy_service": policy_service,
        "template_service": template_service,
        "instantiator": instantiator,
        "deployment_history": deployment_history,
        "deployment_service": deployment_service,
        "verifier": verifier,
        "health_service": health_service,
        "governance_service": governance_service,
        "rollback_service": rollback_service,
        "orchestrator": orchestrator,
    }


def _instantiate(env, scope_id="notebook-1", tool_name="lookup", name="standard-access"):
    created = env["template_service"].create(name, "d", _definition())
    policy = env["instantiator"].instantiate(
        created.template_id, scope_id, {"scope_name": "Notebook", "tool_name": tool_name},
    )
    return created, policy


def _corrupt_rules(env, policy_id):
    """Directly poison a policy's stored rules (bypassing all Commit #1
    validation) while leaving its status ACTIVE -- the only way to make
    an already-deployed, currently-current policy fail Commit #9's own
    rule-validity check without going through any real API."""
    policy = env["policy_service"].get(policy_id)
    policy.rules = [LLMAgentPolicyRule(rule_id="dup", effect=ALLOW), LLMAgentPolicyRule(rule_id="dup", effect=ALLOW)]
    env["policy_service"].store.save(policy)


def test_successful_full_lifecycle():
    env = _services()
    created, policy = _instantiate(env)

    result = env["orchestrator"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    assert result.status == SUCCEEDED
    assert result.policy_id == policy.policy_id
    assert result.scope_id == "notebook-1"
    assert result.deploy_result is not None
    assert result.verification.verified
    assert result.health.status == HEALTHY
    assert result.governance.decision == KEEP
    assert result.rollback is None
    assert result.reasons == []


def test_verification_failure():
    env = _services()
    created, policy = _instantiate(env)
    env["orchestrator"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    # the template evolves after this deployment went live
    env["template_service"].update(
        created.template_id,
        policy_definition=_definition(rules=_definition()["rules"] + [{"rule_id": "extra", "effect": ALLOW}]),
    )

    result = env["orchestrator"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    assert result.status == VERIFICATION_FAILED
    assert not result.verification.verified


def test_degraded_health():
    env = _services()
    created, policy = _instantiate(env)
    env["orchestrator"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    with pytest.raises(DeploymentCompatibilityError):
        env["deployment_service"].deploy(
            policy.policy_id, {"scope_id": "notebook-1", "supported_effects": {"ALLOW"}},
        )

    result = env["orchestrator"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    assert result.status == DEGRADED
    assert result.verification.verified
    assert result.health.status != HEALTHY


def _set_up_rollback_scenario(env):
    created, policy_a = _instantiate(env, tool_name="lookup")
    result_a = env["orchestrator"].deploy(policy_a.policy_id, {"scope_id": "notebook-1"})

    policy_b = env["instantiator"].instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "search"},
    )
    result_b = env["orchestrator"].deploy(policy_b.policy_id, {"scope_id": "notebook-1"})

    _corrupt_rules(env, policy_b.policy_id)

    return created, policy_a, result_a, policy_b, result_b


def test_governance_rejection_without_authorization():
    env = _services()
    created, policy_a, result_a, policy_b, result_b = _set_up_rollback_scenario(env)

    result = env["orchestrator"].deploy(policy_b.policy_id, {"scope_id": "notebook-1"})

    assert result.status == ROLLBACK_RECOMMENDED
    assert result.governance.decision == "rollback_recommended"
    assert result.rollback is None
    assert result.provenance["rollback_target_deployment_id"] == result_a.deploy_result.deployment_id


def test_authorized_rollback():
    env = _services(rollback_authorization=lambda deployment_id, governance: True)
    created, policy_a, result_a, policy_b, result_b = _set_up_rollback_scenario(env)

    result = env["orchestrator"].deploy(policy_b.policy_id, {"scope_id": "notebook-1"})

    assert result.status == ROLLED_BACK
    assert result.rollback is not None
    assert result.rollback.target_policy_id == policy_a.policy_id

    restored_policy_id = env["deployment_service"].current_for("notebook-1", created.name)
    restored = env["policy_service"].get(restored_policy_id)
    assert restored.status == ACTIVE
    assert restored.name == policy_a.name


def test_rollback_failure():
    env = _services(rollback_authorization=lambda deployment_id, governance: True)
    created, policy_a, result_a, policy_b, result_b = _set_up_rollback_scenario(env)

    # make restoration itself impossible: the template can no longer be instantiated
    env["template_service"].archive(created.template_id)

    result = env["orchestrator"].deploy(policy_b.policy_id, {"scope_id": "notebook-1"})

    assert result.status == ROLLBACK_FAILED
    assert any("authorized rollback failed" in reason for reason in result.reasons)
    # the corrupted policy is still whatever it was -- no partial state introduced
    assert env["deployment_service"].current_for("notebook-1", created.name) == policy_b.policy_id


def test_provenance():
    env = _services()
    created, policy = _instantiate(env)

    result = env["orchestrator"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    assert "deploy_result" in result.provenance
    assert "verification" in result.provenance
    assert "health" in result.provenance
    assert "governance" in result.provenance
    assert result.provenance["deploy_result"]["policy_id"] == policy.policy_id


def test_idempotency():
    env = _services()
    created, policy = _instantiate(env)

    first = env["orchestrator"].deploy(policy.policy_id, {"scope_id": "notebook-1"})
    second = env["orchestrator"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    assert first.status == SUCCEEDED
    assert second.status == SUCCEEDED
    assert first.deploy_result.deployment_id == second.deploy_result.deployment_id
    assert second.deploy_result.status == "already_deployed"


def test_existing_deployment_regression():
    env = _services()
    created, policy_direct = _instantiate(env, scope_id="notebook-direct", tool_name="lookup")

    # deploying directly through Commit #7, unmediated by the orchestrator,
    # behaves exactly as it always has
    direct_result = env["deployment_service"].deploy(policy_direct.policy_id, {"scope_id": "notebook-direct"})
    assert direct_result.status == "deployed"
    assert env["policy_service"].get(policy_direct.policy_id).status == ACTIVE

    # a separate, orchestrated deployment in a different scope does not
    # disturb the directly-deployed one at all
    _, policy_orchestrated = _instantiate(env, scope_id="notebook-orchestrated", tool_name="lookup")
    orchestrated_result = env["orchestrator"].deploy(policy_orchestrated.policy_id, {"scope_id": "notebook-orchestrated"})

    assert orchestrated_result.status == SUCCEEDED
    assert env["policy_service"].get(policy_direct.policy_id).status == ACTIVE
    assert env["deployment_service"].current_for("notebook-direct", created.name) == policy_direct.policy_id
