import pytest

from backend.agent_policy_deployment_governance import (
    INVESTIGATE,
    KEEP,
    ROLLBACK_RECOMMENDED,
    LLMAgentPolicyDeploymentGovernance,
)
from backend.agent_policy_deployment_health import LLMAgentPolicyDeploymentHealth
from backend.agent_policy_deployment_history import (
    LLMAgentPolicyDeploymentHistory,
    LLMAgentPolicyDeploymentHistoryTrackedDeploymentService,
)
from backend.agent_policy_deployment_verification import LLMAgentPolicyDeploymentVerifier
from backend.agent_policy_engine import ALLOW, DENY, LLMAgentPolicyService
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


def _services():
    policy_service = LLMAgentPolicyService()
    template_service = LLMAgentPolicyTemplateService(policy_service)
    instantiator = LLMAgentPolicyTemplateInstantiator(template_service)
    deployment_history = LLMAgentPolicyDeploymentHistory()
    deployment_service = LLMAgentPolicyDeploymentHistoryTrackedDeploymentService(
        policy_service, template_service, instantiator, history_service=deployment_history,
    )
    verifier = LLMAgentPolicyDeploymentVerifier(policy_service, template_service, instantiator, deployment_history)
    health_service = LLMAgentPolicyDeploymentHealth(deployment_service, deployment_history, verifier, template_service)
    governance = LLMAgentPolicyDeploymentGovernance(deployment_history, verifier, health_service)
    return {
        "policy_service": policy_service,
        "template_service": template_service,
        "instantiator": instantiator,
        "deployment_history": deployment_history,
        "deployment_service": deployment_service,
        "verifier": verifier,
        "health_service": health_service,
        "governance": governance,
    }


def _instantiate(env, scope_id="notebook-1", tool_name="lookup", name="standard-access"):
    created = env["template_service"].create(name, "d", _definition())
    policy = env["instantiator"].instantiate(
        created.template_id, scope_id, {"scope_name": "Notebook", "tool_name": tool_name},
    )
    return created, policy


def test_healthy_deployment_is_kept():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    decision = env["governance"].evaluate(result.deployment_id)

    assert decision.decision == KEEP
    assert decision.reasons == []
    assert decision.scope_id == "notebook-1"
    assert decision.policy_id == policy.policy_id
    assert decision.template_id == created.template_id


def test_verification_failure_with_prior_success_recommends_rollback():
    env = _services()
    created, policy_a = _instantiate(env, tool_name="lookup")
    result_a = env["deployment_service"].deploy(policy_a.policy_id, {"scope_id": "notebook-1"})

    policy_b = env["instantiator"].instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "search"},
    )
    result_b = env["deployment_service"].deploy(policy_b.policy_id, {"scope_id": "notebook-1"})

    policy_c = env["instantiator"].instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "write"},
    )
    env["deployment_service"].deploy(policy_c.policy_id, {"scope_id": "notebook-1"})

    decision = env["governance"].evaluate(result_b.deployment_id)

    assert decision.decision == ROLLBACK_RECOMMENDED
    assert decision.provenance["prior_successful_deployment_count"] == 1
    assert any("verification failed" in reason for reason in decision.reasons)


def test_verification_failure_without_prior_success_recommends_investigation():
    env = _services()
    created, policy_a = _instantiate(env, tool_name="lookup")
    result_a = env["deployment_service"].deploy(policy_a.policy_id, {"scope_id": "notebook-1"})

    policy_b = env["instantiator"].instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "search"},
    )
    env["deployment_service"].deploy(policy_b.policy_id, {"scope_id": "notebook-1"})

    decision = env["governance"].evaluate(result_a.deployment_id)

    assert decision.decision == INVESTIGATE
    assert decision.provenance["prior_successful_deployment_count"] == 0
    assert any("no earlier successful deployment" in reason for reason in decision.reasons)


def test_degraded_health_from_recent_failures_recommends_investigation():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    with pytest.raises(DeploymentCompatibilityError):
        env["deployment_service"].deploy(
            policy.policy_id, {"scope_id": "notebook-1", "supported_effects": {"ALLOW"}},
        )

    decision = env["governance"].evaluate(result.deployment_id)

    assert decision.decision == INVESTIGATE
    assert any("failed after this one went live" in reason for reason in decision.reasons)


def test_missing_evidence_is_explicit():
    env = _services()

    decision = env["governance"].evaluate("missing-deployment-id")

    assert decision.decision == INVESTIGATE
    assert decision.scope_id is None
    assert decision.policy_id is None
    assert decision.template_id is None
    assert any("no deployment record" in reason for reason in decision.reasons)


def test_provenance():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    decision = env["governance"].evaluate(result.deployment_id)

    assert "verification" in decision.provenance
    assert "health" in decision.provenance
    assert decision.provenance["verification"]["policy_id"] == policy.policy_id
    assert decision.provenance["health"]["policy_id"] == policy.policy_id


def test_deterministic_result():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    first = env["governance"].evaluate(result.deployment_id)
    second = env["governance"].evaluate(result.deployment_id)

    assert first == second


def test_scope_isolation():
    env = _services()
    created_a, policy_a1 = _instantiate(env, scope_id="notebook-a", tool_name="lookup")
    result_a1 = env["deployment_service"].deploy(policy_a1.policy_id, {"scope_id": "notebook-a"})
    policy_a2 = env["instantiator"].instantiate(
        created_a.template_id, "notebook-a", {"scope_name": "Notebook", "tool_name": "search"},
    )
    env["deployment_service"].deploy(policy_a2.policy_id, {"scope_id": "notebook-a"})

    created_b = env["template_service"].create("standard-access-b", "d", _definition())
    policy_b1 = env["instantiator"].instantiate(
        created_b.template_id, "notebook-b", {"scope_name": "Notebook", "tool_name": "lookup"},
    )
    result_b1 = env["deployment_service"].deploy(policy_b1.policy_id, {"scope_id": "notebook-b"})

    # scope-a's superseded deployment should investigate/recommend based only on scope-a history
    decision_a = env["governance"].evaluate(result_a1.deployment_id)
    assert decision_a.decision == INVESTIGATE
    assert decision_a.provenance["prior_successful_deployment_count"] == 0

    # scope-b's own still-current deployment is unaffected
    decision_b = env["governance"].evaluate(result_b1.deployment_id)
    assert decision_b.decision == KEEP
