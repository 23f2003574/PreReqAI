from backend.agent_policy_deployment_history import (
    DEPLOYMENT_FAILED,
    DEPLOYMENT_SUCCEEDED,
    LLMAgentPolicyDeploymentHistory,
    LLMAgentPolicyDeploymentHistoryTrackedDeploymentService,
)
from backend.agent_policy_deployment_verification import LLMAgentPolicyDeploymentVerifier, VerificationResult
from backend.agent_policy_engine import (
    ACTIVE,
    ALLOW,
    ARCHIVED,
    DENY,
    InMemoryLLMAgentPolicyStore,
    LLMAgentPolicy,
    LLMAgentPolicyRule,
    LLMAgentPolicyService,
)
from backend.agent_policy_history import LLMAgentPolicyHistoryService, LLMAgentPolicyHistoryTrackedService
from backend.agent_policy_template_instantiation_pipeline import LLMAgentPolicyTemplateInstantiator
from backend.agent_policy_templates import LLMAgentPolicyTemplateService
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


def _services(with_versioning=False):
    store = InMemoryLLMAgentPolicyStore()
    base_history = LLMAgentPolicyHistoryService()
    tracked_policy_service = LLMAgentPolicyHistoryTrackedService(store=store, history_service=base_history)
    bare_policy_service = LLMAgentPolicyService(store=store)
    version_service = LLMAgentPolicyVersionService(bare_policy_service, base_history) if with_versioning else None

    template_service = LLMAgentPolicyTemplateService(tracked_policy_service if with_versioning else bare_policy_service)
    instantiator = LLMAgentPolicyTemplateInstantiator(template_service, version_service=version_service)
    deployment_history = LLMAgentPolicyDeploymentHistory()
    deployment_service = LLMAgentPolicyDeploymentHistoryTrackedDeploymentService(
        bare_policy_service, template_service, instantiator,
        history_service=deployment_history, version_service=version_service,
    )
    verifier = LLMAgentPolicyDeploymentVerifier(
        bare_policy_service, template_service, instantiator, deployment_history, version_service=version_service,
    )
    return {
        "store": store,
        "tracked_policy_service": tracked_policy_service,
        "bare_policy_service": bare_policy_service,
        "version_service": version_service,
        "template_service": template_service,
        "instantiator": instantiator,
        "deployment_history": deployment_history,
        "deployment_service": deployment_service,
        "verifier": verifier,
    }


def _instantiate(env, scope_id="notebook-1", tool_name="lookup", name="standard-access"):
    created = env["template_service"].create(name, "d", _definition())
    policy = env["instantiator"].instantiate(
        created.template_id, scope_id, {"scope_name": "Notebook", "tool_name": tool_name},
    )
    return created, policy


def test_valid_deployment():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    verification = env["verifier"].verify(result.deployment_id)

    assert isinstance(verification, VerificationResult)
    assert verification.verified
    assert verification.reasons == []
    assert verification.policy_id == policy.policy_id
    assert verification.provenance["intended_template_id"] == created.template_id
    assert verification.provenance["actual_template_id"] == created.template_id


def test_wrong_active_version():
    env = _services(with_versioning=True)
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    # drift: the deployed policy's rules are changed after deployment,
    # bumping its Commit #11 version past what was recorded at deploy time
    env["tracked_policy_service"].update(
        policy.policy_id, rules=list(policy.rules) + [LLMAgentPolicyRule(rule_id="extra", effect=ALLOW)],
    )

    verification = env["verifier"].verify(result.deployment_id)

    assert not verification.verified
    assert any("version" in reason for reason in verification.reasons)
    assert verification.provenance["intended_policy_version"] == 1
    assert verification.provenance["actual_policy_version"] == 2


def test_wrong_scope():
    env = _services()
    created, policy = _instantiate(env)
    # a forged deployment record claiming the wrong target scope
    record = env["deployment_history"].record(
        policy_id=policy.policy_id, target_scope="wrong-scope", status=DEPLOYMENT_SUCCEEDED,
        template_id=created.template_id, template_version=created.version,
    )

    verification = env["verifier"].verify(record.deployment_id)

    assert not verification.verified
    assert any("scope" in reason for reason in verification.reasons)
    assert verification.provenance["intended_scope"] == "wrong-scope"
    assert verification.provenance["actual_scope"] == "notebook-1"


def test_provenance_mismatch():
    env = _services()
    created, policy = _instantiate(env)
    record = env["deployment_history"].record(
        policy_id=policy.policy_id, target_scope="notebook-1", status=DEPLOYMENT_SUCCEEDED,
        template_id="some-other-template-id", template_version=99,
    )

    verification = env["verifier"].verify(record.deployment_id)

    assert not verification.verified
    assert any("template" in reason for reason in verification.reasons)
    assert verification.provenance["intended_template_id"] == "some-other-template-id"
    assert verification.provenance["actual_template_id"] == created.template_id


def test_invalid_active_policy():
    env = _services()
    broken_policy = LLMAgentPolicy(
        scope_id="notebook-1", name="broken",
        rules=[{"rule_id": "dup", "effect": ALLOW}, {"rule_id": "dup", "effect": ALLOW}],
    )
    env["store"].save(broken_policy)
    record = env["deployment_history"].record(
        policy_id=broken_policy.policy_id, target_scope="notebook-1", status=DEPLOYMENT_SUCCEEDED,
    )

    verification = env["verifier"].verify(record.deployment_id)

    assert not verification.verified
    assert any("valid rules" in reason for reason in verification.reasons)


def test_incomplete_deployment():
    env = _services()
    created, policy = _instantiate(env)
    record = env["deployment_history"].record(
        policy_id=policy.policy_id, target_scope="notebook-1", status=DEPLOYMENT_FAILED,
        provenance={"reason": "simulated failure"},
    )

    verification = env["verifier"].verify(record.deployment_id)

    assert not verification.verified
    assert any("terminal state" in reason for reason in verification.reasons)
    assert verification.provenance["recorded_status"] == DEPLOYMENT_FAILED


def test_unknown_deployment_id():
    env = _services()
    verification = env["verifier"].verify("missing-deployment-id")

    assert not verification.verified
    assert verification.policy_id is None
    assert any("was ever recorded" in reason for reason in verification.reasons)


def test_archived_policy_fails_verification():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    env["bare_policy_service"].archive(policy.policy_id)

    verification = env["verifier"].verify(result.deployment_id)

    assert not verification.verified
    assert any("not ACTIVE" in reason for reason in verification.reasons)
    assert verification.provenance["policy_status"] == ARCHIVED


def test_repeated_verification_is_deterministic():
    env = _services()
    created, policy = _instantiate(env)
    result = env["deployment_service"].deploy(policy.policy_id, {"scope_id": "notebook-1"})

    first = env["verifier"].verify(result.deployment_id)
    second = env["verifier"].verify(result.deployment_id)

    assert first == second
