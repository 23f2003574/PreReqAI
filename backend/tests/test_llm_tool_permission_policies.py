import pytest

from backend.llm.tool_invocation import LLMToolInvocationService, READY, REJECTED
from backend.llm.tool_permissions import (
    ANY_SUBJECT,
    AUTHORIZED,
    CONDITIONAL,
    DENIED,
    DuplicateToolPolicyError,
    InvalidToolPolicyError,
    LLMToolPermissionPolicy,
    LLMToolPermissionService,
    UnknownToolPolicyError,
)
from backend.llm.tools import LLMToolRegistryService, UnknownToolError

# As in Commits #1-#3, the tool describes a real project capability --
# LLMAPICandidateService.analyze(analysis_id).
DETECT_API_CANDIDATES_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis_id": {"type": "string", "description": "A prior notebook analysis id."},
        "min_confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
    "required": ["analysis_id"],
}


def _setup(enabled=True):
    registry = LLMToolRegistryService()
    registry.register(
        "detect_api_candidates",
        "Identify API-worthy functions via LLMAPICandidateService.",
        DETECT_API_CANDIDATES_SCHEMA,
        enabled=enabled,
    )
    invocation = LLMToolInvocationService(registry)
    permissions = LLMToolPermissionService(registry, invocation)
    return registry, invocation, permissions


def _plan(invocation, **arguments):
    return invocation.plan(
        {
            "name": "detect_api_candidates",
            "arguments": arguments or {"analysis_id": "analysis-1"},
        }
    )


def _policy(policy_id="policy-1", subject="user:ada", allowed=True, conditions=None):
    return LLMToolPermissionPolicy(
        policy_id=policy_id,
        tool_name="detect_api_candidates",
        subject=subject,
        allowed=allowed,
        conditions=conditions or {},
    )


def test_allowed_invocation():
    _, invocation, permissions = _setup()
    permissions.register(_policy())

    result = permissions.authorize(_plan(invocation), "user:ada")

    assert result.allowed is True
    assert result.decision == AUTHORIZED
    assert result.policy_id == "policy-1"
    assert "allows subject" in result.reason


def test_allowed_via_a_scope_the_subject_holds():
    """A caller is usually several things at once -- a user and its roles."""
    _, invocation, permissions = _setup()
    permissions.register(_policy(subject="role:maintainer"))

    result = permissions.authorize(
        _plan(invocation), ["user:ada", "role:maintainer"]
    )

    assert result.allowed is True
    assert result.policy_id == "policy-1"


def test_wildcard_subject_is_a_tool_wide_default():
    _, invocation, permissions = _setup()
    permissions.register(_policy(subject=ANY_SUBJECT))

    result = permissions.authorize(_plan(invocation), "user:anyone")

    assert result.allowed is True
    assert result.decision == AUTHORIZED


def test_denied_invocation():
    _, invocation, permissions = _setup()
    permissions.register(_policy(allowed=False))

    result = permissions.authorize(_plan(invocation), "user:ada")

    assert result.allowed is False
    assert result.decision == DENIED
    assert result.policy_id == "policy-1"
    assert "explicitly denies" in result.reason


def test_explicit_deny_precedence():
    """A deny wins over any allow, however specific or however recent."""
    _, invocation, permissions = _setup()

    # Registered allow-first, then deny.
    permissions.register(_policy("allow-1", subject="user:ada", allowed=True))
    permissions.register(_policy("deny-1", subject="user:ada", allowed=False))

    result = permissions.authorize(_plan(invocation), "user:ada")
    assert result.allowed is False
    assert result.policy_id == "deny-1"

    # ...and the other registration order gives the same answer, so a deny
    # can never be overridden by adding another allow after it.
    _, invocation2, permissions2 = _setup()
    permissions2.register(_policy("deny-2", subject="user:ada", allowed=False))
    permissions2.register(_policy("allow-2", subject="user:ada", allowed=True))

    later = permissions2.authorize(_plan(invocation2), "user:ada")
    assert later.allowed is False
    assert later.policy_id == "deny-2"


def test_specific_deny_beats_wildcard_allow():
    _, invocation, permissions = _setup()
    permissions.register(_policy("allow-all", subject=ANY_SUBJECT, allowed=True))
    permissions.register(_policy("deny-ada", subject="user:ada", allowed=False))

    assert permissions.authorize(_plan(invocation), "user:ada").allowed is False
    assert permissions.authorize(_plan(invocation), "user:grace").allowed is True


def test_missing_policy_denies_by_default():
    _, invocation, permissions = _setup()

    result = permissions.authorize(_plan(invocation), "user:ada")

    assert result.allowed is False
    assert result.decision == DENIED
    assert result.policy_id is None
    assert "denied by default" in result.reason


def test_policy_for_another_subject_does_not_apply():
    _, invocation, permissions = _setup()
    permissions.register(_policy(subject="user:grace"))

    result = permissions.authorize(_plan(invocation), "user:ada")

    assert result.allowed is False
    assert result.policy_id is None


def test_disabled_tool_stays_unavailable_despite_an_allow_policy():
    registry, invocation, permissions = _setup()
    permissions.register(_policy())
    plan = _plan(invocation)
    assert permissions.authorize(plan, "user:ada").allowed is True

    registry.disable("detect_api_candidates")

    result = permissions.authorize(plan, "user:ada")
    assert result.allowed is False
    assert result.decision == DENIED
    assert "disabled" in result.reason
    assert result.policy_id is None


def test_unknown_tool_is_denied():
    registry, invocation, permissions = _setup()
    registry.register(
        "analyze_notebook",
        "Analyze a notebook via LLMNotebookAnalysisService.",
        {"type": "object", "properties": {"notebook": {"type": "object"}}},
    )
    plan = invocation.plan({"name": "analyze_notebook", "arguments": {"notebook": {}}})
    # Drop the tool from the registry after the plan was made.
    registry._tools.pop(registry._id_by_name.pop("analyze_notebook"))

    result = permissions.authorize(plan, "user:ada")

    assert result.allowed is False
    assert "not registered" in result.reason


def test_revoked_policy():
    _, invocation, permissions = _setup()
    permissions.register(_policy())
    assert permissions.authorize(_plan(invocation), "user:ada").allowed is True

    revoked = permissions.revoke("policy-1")

    assert revoked.policy_id == "policy-1"
    assert permissions.policies("detect_api_candidates") == ()
    # Revocation takes effect immediately.
    assert permissions.authorize(_plan(invocation), "user:ada").allowed is False

    with pytest.raises(UnknownToolPolicyError):
        permissions.revoke("policy-1")


def test_revoking_a_deny_restores_an_allow():
    _, invocation, permissions = _setup()
    permissions.register(_policy("allow-1", allowed=True))
    permissions.register(_policy("deny-1", allowed=False))
    assert permissions.authorize(_plan(invocation), "user:ada").allowed is False

    permissions.revoke("deny-1")

    assert permissions.authorize(_plan(invocation), "user:ada").allowed is True


def test_conditions_narrow_a_policy():
    _, invocation, permissions = _setup()
    permissions.register(
        _policy(conditions={"analysis_id": ["analysis-1", "analysis-2"]})
    )

    matched = permissions.authorize(_plan(invocation, analysis_id="analysis-1"), "user:ada")
    assert matched.allowed is True
    assert matched.decision == CONDITIONAL
    assert "conditions" in matched.reason

    unmatched = permissions.authorize(_plan(invocation, analysis_id="analysis-9"), "user:ada")
    assert unmatched.allowed is False
    assert unmatched.policy_id is None


def test_conditioned_deny_applies_only_to_matching_calls():
    _, invocation, permissions = _setup()
    permissions.register(_policy("allow-all", subject=ANY_SUBJECT, allowed=True))
    permissions.register(
        _policy("deny-secret", subject=ANY_SUBJECT, allowed=False,
                conditions={"analysis_id": "analysis-secret"})
    )

    assert permissions.authorize(
        _plan(invocation, analysis_id="analysis-secret"), "user:ada"
    ).allowed is False
    assert permissions.authorize(
        _plan(invocation, analysis_id="analysis-1"), "user:ada"
    ).allowed is True


def test_condition_on_an_absent_argument_does_not_apply():
    _, invocation, permissions = _setup()
    permissions.register(_policy(conditions={"min_confidence": 0.9}))

    result = permissions.authorize(_plan(invocation, analysis_id="analysis-1"), "user:ada")

    assert result.allowed is False
    assert result.policy_id is None


def test_a_rejected_plan_is_never_authorized():
    """Authorization does not rescue a call that failed schema validation."""
    _, invocation, permissions = _setup()
    permissions.register(_policy(subject=ANY_SUBJECT))
    rejected = invocation.plan({"name": "detect_api_candidates", "arguments": {}})
    assert rejected.status == REJECTED

    result = permissions.authorize(rejected, "user:ada")

    assert result.allowed is False
    assert REJECTED in result.reason


def test_a_stale_plan_is_denied_via_the_invocation_service():
    """A plan that no longer validates is denied even though the tool is
    enabled and an allow policy exists."""
    registry, invocation, permissions = _setup()
    permissions.register(_policy())
    plan = _plan(invocation)
    assert plan.status == READY
    assert permissions.authorize(plan, "user:ada").allowed is True

    # Break the stored definition so Commit #3's validate() now fails.
    import dataclasses

    tool = registry.get("detect_api_candidates")
    registry._tools[tool.tool_id] = dataclasses.replace(
        tool, input_schema={"type": "object", "properties": {"analysis_id": {"type": "str"}}}
    )

    result = permissions.authorize(plan, "user:ada")
    assert result.allowed is False
    assert "no longer valid" in result.reason


def test_register_requires_an_existing_tool():
    _, _, permissions = _setup()

    with pytest.raises(UnknownToolError):
        permissions.register(
            LLMToolPermissionPolicy(
                policy_id="policy-x",
                tool_name="does_not_exist",
                subject="user:ada",
                allowed=True,
            )
        )

    assert permissions.policies("detect_api_candidates") == ()


def test_a_policy_may_be_written_for_a_currently_disabled_tool():
    registry, _, permissions = _setup(enabled=False)

    policy = permissions.register(_policy())

    assert permissions.policies("detect_api_candidates") == (policy,)


def test_duplicate_policy_id_rejected():
    _, _, permissions = _setup()
    permissions.register(_policy())

    with pytest.raises(DuplicateToolPolicyError):
        permissions.register(_policy(subject="user:grace"))

    assert len(permissions.policies("detect_api_candidates")) == 1


def test_policies_listing_is_per_tool_and_in_registration_order():
    registry, _, permissions = _setup()
    registry.register(
        "analyze_notebook",
        "Analyze a notebook via LLMNotebookAnalysisService.",
        {"type": "object", "properties": {"notebook": {"type": "object"}}},
    )
    first = permissions.register(_policy("policy-1", subject="user:ada"))
    other = permissions.register(
        LLMToolPermissionPolicy(
            policy_id="policy-2", tool_name="analyze_notebook",
            subject="user:ada", allowed=True,
        )
    )
    second = permissions.register(_policy("policy-3", subject="user:grace"))

    assert permissions.policies("detect_api_candidates") == (first, second)
    assert permissions.policies("analyze_notebook") == (other,)

    with pytest.raises(UnknownToolError):
        permissions.policies("does_not_exist")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"policy_id": ""},
        {"policy_id": None},
        {"tool_name": "  "},
        {"subject": ""},
        {"allowed": "yes"},
        {"conditions": "not-a-dict"},
        {"conditions": {"": 1}},
    ],
)
def test_malformed_policy_rejected(kwargs):
    base = {
        "policy_id": "policy-1",
        "tool_name": "detect_api_candidates",
        "subject": "user:ada",
        "allowed": True,
    }
    base.update(kwargs)

    with pytest.raises(InvalidToolPolicyError):
        LLMToolPermissionPolicy(**base)


def test_authorize_rejects_malformed_input():
    _, invocation, permissions = _setup()
    plan = _plan(invocation)

    with pytest.raises(InvalidToolPolicyError):
        permissions.authorize({"tool_name": "detect_api_candidates"}, "user:ada")

    for bad_subject in ("", "   ", [], 42, ["user:ada", ""]):
        with pytest.raises(InvalidToolPolicyError):
            permissions.authorize(plan, bad_subject)

    with pytest.raises(InvalidToolPolicyError):
        permissions.register({"policy_id": "not-a-policy"})


def test_authorization_executes_nothing():
    """Authorization runs before execution and performs none -- the service
    has no dispatch surface and mutates neither plan nor registry."""
    registry, invocation, permissions = _setup()
    permissions.register(_policy())
    plan = _plan(invocation)

    for attr in ("invoke", "call", "execute", "run", "dispatch", "apply"):
        assert not hasattr(permissions, attr)

    before = (plan.tool_name, dict(plan.arguments), plan.status)
    permissions.authorize(plan, "user:ada")

    assert (plan.tool_name, dict(plan.arguments), plan.status) == before
    assert [tool.name for tool in registry.list()] == ["detect_api_candidates"]
    assert registry.get("detect_api_candidates").enabled is True
