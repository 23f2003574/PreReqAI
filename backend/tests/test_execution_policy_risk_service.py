from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyAuditEvent,
    ExecutionPolicyAuditService,
    ExecutionPolicyConflictService,
    ExecutionPolicyEvaluationService,
    ExecutionPolicyExceptionService,
    ExecutionPolicyRiskError as Error,
    ExecutionPolicyRiskScore,
    ExecutionPolicyRiskService,
    ExecutionPolicyService,
)


class _FakeSessionService:
    def __init__(self, actions_by_session):
        self._actions_by_session = actions_by_session

    def requested_actions(self, session_id):
        return self._actions_by_session.get(session_id, [])


def _build(actions_by_session=None):
    policy_service = ExecutionPolicyService()
    session_service = _FakeSessionService(actions_by_session or {})
    evaluation_service = ExecutionPolicyEvaluationService(policy_service, session_service)
    conflict_service = ExecutionPolicyConflictService(policy_service)
    exception_service = ExecutionPolicyExceptionService(policy_service)
    audit_service = ExecutionPolicyAuditService()
    risk_service = ExecutionPolicyRiskService(
        evaluation_service,
        conflict_service,
        exception_service,
        audit_service,
    )
    return {
        "policy": policy_service,
        "evaluation": evaluation_service,
        "conflict": conflict_service,
        "exception": exception_service,
        "audit": audit_service,
        "risk": risk_service,
    }


def _register(policy_service, policy_id, rules=("read",)):
    return policy_service.register(
        ExecutionPolicy(
            policy_id=policy_id,
            name=policy_id,
            rules=frozenset(rules),
        )
    )


class TestExecutionPolicyRiskService:
    def test_low_risk_session(self):
        services = _build(actions_by_session={"session-1": ["read"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["evaluation"].evaluate("policy-1", "session-1")

        risk_score = services["risk"].calculate("session-1")

        assert isinstance(risk_score, ExecutionPolicyRiskScore)
        assert risk_score.score == 0
        assert risk_score.level == "LOW"

    def test_violation_impact(self):
        services = _build(actions_by_session={"session-1": ["read", "delete", "admin"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["evaluation"].evaluate("policy-1", "session-1")

        breakdown = services["risk"].factor_breakdown("session-1")
        assert breakdown["violations"] == 2

        risk_score = services["risk"].calculate("session-1")
        assert risk_score.score == 20
        assert risk_score.level == "LOW"

    def test_conflict_impact(self):
        services = _build()
        _register(services["policy"], "policy-a", rules=("delete",))
        _register(services["policy"], "policy-b", rules=("!delete",))
        services["conflict"].detect(["policy-a", "policy-b"], scope_id="session-1")

        risk_score = services["risk"].calculate("session-1")

        assert risk_score.score == 25
        assert risk_score.level == "MEDIUM"
        assert risk_score.factors["unresolved_conflicts"] == 1

    def test_expired_exception_impact(self):
        services = _build()
        _register(services["policy"], "policy-1")
        services["exception"].create(
            "policy-1",
            "session-1",
            "delete",
            "temporary",
            datetime.now(timezone.utc) - timedelta(seconds=1),
        )

        risk_score = services["risk"].calculate("session-1")

        assert risk_score.score == 15
        assert risk_score.level == "LOW"
        assert risk_score.factors["expired_exceptions"] == 1

    def test_denied_enforcement_impact(self):
        services = _build()
        services["audit"].record(
            ExecutionPolicyAuditEvent(
                event_id="event-1",
                session_id="session-1",
                policy_ids=("policy-1",),
                event_type="enforcement",
                decision="denied",
            )
        )

        risk_score = services["risk"].calculate("session-1")

        assert risk_score.score == 20
        assert risk_score.factors["denied_enforcement_events"] == 1

    def test_level_thresholds(self):
        services = _build()
        pairs = [("policy-a1", "policy-b1"), ("policy-a2", "policy-b2"), ("policy-a3", "policy-b3")]

        for first, second in pairs:
            _register(services["policy"], first, rules=("delete",))
            _register(services["policy"], second, rules=("!delete",))

        assert services["risk"].level("session-1") == "LOW"

        services["conflict"].detect(list(pairs[0]), scope_id="session-1")
        assert services["risk"].level("session-1") == "MEDIUM"

        services["conflict"].detect(list(pairs[1]), scope_id="session-1")
        assert services["risk"].level("session-1") == "HIGH"

        services["conflict"].detect(list(pairs[2]), scope_id="session-1")
        assert services["risk"].level("session-1") == "CRITICAL"

    def test_score_is_capped_at_max(self):
        services = _build()
        pairs = [(f"policy-a{i}", f"policy-b{i}") for i in range(6)]

        for first, second in pairs:
            _register(services["policy"], first, rules=("delete",))
            _register(services["policy"], second, rules=("!delete",))
            services["conflict"].detect([first, second], scope_id="session-1")

        risk_score = services["risk"].calculate("session-1")

        assert risk_score.score == 100
        assert risk_score.level == "CRITICAL"

    def test_history(self):
        services = _build()

        first = services["risk"].calculate("session-1")
        second = services["risk"].calculate("session-1")

        assert services["risk"].history("session-1") == [first, second]

    def test_deterministic_score(self):
        services = _build(actions_by_session={"session-1": ["read", "delete"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["evaluation"].evaluate("policy-1", "session-1")

        first = services["risk"].calculate("session-1")
        second = services["risk"].calculate("session-1")

        assert first.score == second.score
        assert first.level == second.level
        assert first.factors == second.factors

    def test_calculate_rejects_blank_session_id(self):
        services = _build()

        with pytest.raises(Error):
            services["risk"].calculate("")
