import pytest

from backend.agent_policy_deployment_health import (
    DEGRADED,
    HEALTHY,
    UNHEALTHY,
    UNKNOWN,
    LLMAgentPolicyDeploymentHealth,
)
from backend.agent_policy_deployment_history import (
    LLMAgentPolicyDeploymentHistory,
    LLMAgentPolicyDeploymentHistoryTrackedDeploymentService,
)
from backend.agent_policy_deployment_verification import LLMAgentPolicyDeploymentVerifier
from backend.agent_policy_engine import ACTIVE, ALLOW, DENY, LLMAgentPolicyService
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
    health = LLMAgentPolicyDeploymentHealth(deployment_service, deployment_history, verifier, template_service)
    return {
        "policy_service": policy_service,
        "template_service": template_service,
        "instantiator": instantiator,
        "deployment_history": deployment_history,
        "deployment_service": deployment_service,
        "verifier": verifier,
        "health": health,
    }


def _instantiate(env, scope_id="notebook-1", tool_name="lookup", name="standard-access"):
    created = env["template_service"].create(name, "d", _definition())
    policy = env["instantiator"].instantiate(
        created.template_id, scope_id, {"scope_name": "Notebook", "tool_name": tool_name},
    )
    return created, policy


def test_healthy_deployment():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    health = env["health"].assess(result.deployment_id)

    assert health.status == HEALTHY
    assert health.reasons == []
    assert health.policy_id == policy.policy_id
    assert health.scope_id == "notebook-1"
    assert health.template_id == created.template_id
    assert health.template_version == created.version


def test_verification_failure_is_unhealthy():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    env["policy_service"].archive(policy.policy_id)

    health = env["health"].assess(result.deployment_id)

    assert health.status == UNHEALTHY
    assert any("still supposed to be active" in reason for reason in health.reasons)


def test_version_mismatch_is_unhealthy():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    # the template evolves after this deployment went live
    env["template_service"].update(
        created.template_id,
        policy_definition=_definition(rules=_definition()["rules"] + [{"rule_id": "extra", "effect": ALLOW}]),
    )

    health = env["health"].assess(result.deployment_id)

    assert health.status == UNHEALTHY
    assert any("verification failed" in reason for reason in health.reasons)


def test_recent_deployment_failure_degrades_health():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    with pytest.raises(DeploymentCompatibilityError):
        env["deployment_service"].deploy(
            policy.policy_id, {"scope_id": "notebook-1", "supported_effects": {"ALLOW"}},
        )

    health = env["health"].assess(result.deployment_id)

    assert health.status == DEGRADED
    assert any("failed after this one went live" in reason for reason in health.reasons)
    assert health.provenance["later_failure_count"] == 1


def test_rollback_state_degrades_health():
    env = _services()
    created, policy_a = _instantiate(env, tool_name="lookup")
    result_a = env["deployment_service"].deploy(policy_a.policy_id, {"scope_id": "notebook-1"})

    policy_b = env["instantiator"].instantiate(
        created.template_id, "notebook-1", {"scope_name": "Notebook", "tool_name": "search"},
    )
    env["deployment_service"].deploy(policy_b.policy_id, {"scope_id": "notebook-1"})

    health = env["health"].assess(result_a.deployment_id)

    assert health.status == DEGRADED
    assert any("no longer the active one" in reason for reason in health.reasons)


def test_empty_scope():
    env = _services()
    results = env["health"].assess_scope("no-such-scope")
    assert results == []


def test_unknown_deployment_id():
    env = _services()
    health = env["health"].assess("missing-deployment-id")

    assert health.status == UNKNOWN
    assert health.policy_id is None
    assert any("no deployment record" in reason for reason in health.reasons)


def test_deterministic_result():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    first = env["health"].assess(result.deployment_id)
    second = env["health"].assess(result.deployment_id)

    assert first == second


def test_assess_scope_ordering_and_isolation():
    env = _services()
    created_a, policy_a = _instantiate(env, scope_id="notebook-a")
    result_a = env["deployment_service"].deploy(policy_a.policy_id, {"scope_id": "notebook-a"})

    created_b = env["template_service"].create("standard-access-b", "d", _definition())
    policy_b = env["instantiator"].instantiate(
        created_b.template_id, "notebook-b", {"scope_name": "Notebook", "tool_name": "lookup"},
    )
    env["deployment_service"].deploy(policy_b.policy_id, {"scope_id": "notebook-b"})

    results_a = env["health"].assess_scope("notebook-a")
    assert [r.deployment_id for r in results_a] == [result_a.deployment_id]
    assert all(r.scope_id == "notebook-a" for r in results_a)


def test_provenance():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    health = env["health"].assess(result.deployment_id)

    assert health.provenance["recorded_status"] == "deployment_succeeded"
    assert "verification" in health.provenance
    assert health.provenance["current_policy_id"] == policy.policy_id
    assert health.provenance["later_failure_count"] == 0
