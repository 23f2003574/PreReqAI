from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyAuditService,
    ExecutionPolicyConflictService,
    ExecutionPolicyEvaluationService,
    ExecutionPolicyExceptionService,
    ExecutionPolicyRiskOverrideService,
    ExecutionPolicyRiskReport,
    ExecutionPolicyRiskReportError as Error,
    ExecutionPolicyRiskReportService,
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
    risk_service = ExecutionPolicyRiskService(evaluation_service, conflict_service, exception_service, audit_service)
    override_service = ExecutionPolicyRiskOverrideService()
    report_service = ExecutionPolicyRiskReportService(
        evaluation_service,
        conflict_service,
        risk_service,
        override_service,
    )
    return {
        "policy": policy_service,
        "evaluation": evaluation_service,
        "conflict": conflict_service,
        "override": override_service,
        "risk": risk_service,
        "report": report_service,
    }


def _register(policy_service, policy_id, rules=("read",)):
    return policy_service.register(
        ExecutionPolicy(
            policy_id=policy_id,
            name=policy_id,
            rules=frozenset(rules),
        )
    )


class TestExecutionPolicyRiskReportService:
    def test_generate_report(self):
        services = _build(actions_by_session={"session-1": ["read"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["evaluation"].evaluate("policy-1", "session-1")

        report = services["report"].generate("session-1")

        assert isinstance(report, ExecutionPolicyRiskReport)
        assert report.session_id == "session-1"

    def test_generate_unknown_session_is_rejected(self):
        services = _build()

        with pytest.raises(Error):
            services["report"].generate("never-evaluated-session")

    def test_risk_score_inclusion(self):
        services = _build()
        _register(services["policy"], "policy-a", rules=("delete",))
        _register(services["policy"], "policy-b", rules=("!delete",))
        services["evaluation"].evaluate("policy-a", "session-1")
        services["conflict"].detect(["policy-a", "policy-b"], scope_id="session-1")

        report = services["report"].generate("session-1")
        risk_score = services["risk"].calculate("session-1")

        assert report.risk_score == risk_score.score
        assert report.risk_level == risk_score.level

    def test_violations_and_conflicts_inclusion(self):
        services = _build(actions_by_session={"session-1": ["read", "delete"]})
        _register(services["policy"], "policy-1", rules=("read",))
        _register(services["policy"], "policy-a", rules=("admin",))
        _register(services["policy"], "policy-b", rules=("!admin",))
        services["evaluation"].evaluate("policy-1", "session-1")
        conflicts = services["conflict"].detect(["policy-a", "policy-b"], scope_id="session-1")

        report = services["report"].generate("session-1")

        assert report.violations == ("policy-1:unpermitted_action:delete",)
        assert report.conflicts == (conflicts[0].conflict_id,)

    def test_override_inclusion(self):
        services = _build()
        _register(services["policy"], "policy-1")
        services["evaluation"].evaluate("policy-1", "session-1")

        override = services["override"].create(
            "session-1",
            "MEDIUM",
            "approved tolerance",
            datetime.now(timezone.utc) + timedelta(hours=1),
        )

        report = services["report"].generate("session-1")

        assert report.overrides == (override.override_id,)

    def test_deterministic_output(self):
        services = _build(actions_by_session={"session-1": ["read", "delete"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["evaluation"].evaluate("policy-1", "session-1")

        first = services["report"].generate("session-1")
        second = services["report"].generate("session-1")

        assert first.violations == second.violations
        assert first.conflicts == second.conflicts
        assert first.overrides == second.overrides
        assert first.risk_score == second.risk_score
        assert first.risk_level == second.risk_level

    def test_history(self):
        services = _build()
        _register(services["policy"], "policy-1")
        services["evaluation"].evaluate("policy-1", "session-1")

        first = services["report"].generate("session-1")
        second = services["report"].generate("session-1")

        assert services["report"].history("session-1") == [first, second]

    def test_get_unknown_report_is_an_error(self):
        services = _build()

        with pytest.raises(Error):
            services["report"].get("unknown-report")

    def test_report_comparison(self):
        services = _build()
        _register(services["policy"], "policy-a", rules=("delete",))
        _register(services["policy"], "policy-b", rules=("!delete",))
        services["evaluation"].evaluate("policy-a", "session-1")

        before = services["report"].generate("session-1")

        conflicts = services["conflict"].detect(["policy-a", "policy-b"], scope_id="session-1")
        after = services["report"].generate("session-1")

        comparison = services["report"].compare(before.report_id, after.report_id)

        assert comparison["new_conflicts"] == (conflicts[0].conflict_id,)
        assert comparison["resolved_conflicts"] == ()
        assert comparison["risk_score_delta"] == after.risk_score - before.risk_score

    def test_compare_unknown_report_is_an_error(self):
        services = _build()
        _register(services["policy"], "policy-1")
        services["evaluation"].evaluate("policy-1", "session-1")
        report = services["report"].generate("session-1")

        with pytest.raises(Error):
            services["report"].compare(report.report_id, "unknown-report")
