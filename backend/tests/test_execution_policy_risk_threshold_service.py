import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyConflictService,
    ExecutionPolicyEvaluationService,
    ExecutionPolicyExceptionService,
    ExecutionPolicyAuditService,
    ExecutionPolicyRiskService,
    ExecutionPolicyRiskThreshold,
    ExecutionPolicyRiskThresholdError as Error,
    ExecutionPolicyRiskThresholdService,
    ExecutionPolicyService,
)


class _FakeSessionService:
    def requested_actions(self, session_id):
        return []


def _build():
    policy_service = ExecutionPolicyService()
    evaluation_service = ExecutionPolicyEvaluationService(policy_service, _FakeSessionService())
    conflict_service = ExecutionPolicyConflictService(policy_service)
    exception_service = ExecutionPolicyExceptionService(policy_service)
    audit_service = ExecutionPolicyAuditService()
    risk_service = ExecutionPolicyRiskService(evaluation_service, conflict_service, exception_service, audit_service)
    threshold_service = ExecutionPolicyRiskThresholdService(risk_service)
    return {
        "policy": policy_service,
        "conflict": conflict_service,
        "risk": risk_service,
        "threshold": threshold_service,
    }


def _register_policy(policy_service, policy_id, rules):
    return policy_service.register(
        ExecutionPolicy(
            policy_id=policy_id,
            name=policy_id,
            rules=frozenset(rules),
        )
    )


def _add_conflicts(services, session_id, count):
    for i in range(count):
        first, second = f"policy-a{i}", f"policy-b{i}"
        _register_policy(services["policy"], first, ("delete",))
        _register_policy(services["policy"], second, ("!delete",))
        services["conflict"].detect([first, second], scope_id=session_id)


class TestExecutionPolicyRiskThresholdService:
    def test_register_threshold(self):
        services = _build()
        threshold = ExecutionPolicyRiskThreshold(
            threshold_id="threshold-1",
            level="MEDIUM",
            minimum_score=25,
            action="WARN",
        )

        registered = services["threshold"].register(threshold)

        assert registered is threshold
        assert services["threshold"].thresholds() == [threshold]

    def test_register_duplicate_id_is_rejected(self):
        services = _build()
        threshold = ExecutionPolicyRiskThreshold(
            threshold_id="threshold-1",
            level="MEDIUM",
            minimum_score=25,
            action="WARN",
        )
        services["threshold"].register(threshold)

        with pytest.raises(Error):
            services["threshold"].register(threshold)

    def test_matching_threshold(self):
        services = _build()
        services["threshold"].register(
            ExecutionPolicyRiskThreshold(
                threshold_id="threshold-1",
                level="MEDIUM",
                minimum_score=25,
                action="WARN",
            )
        )
        _add_conflicts(services, "session-1", 1)

        assert services["threshold"].evaluate("session-1") == "WARN"

    def test_no_match_defaults_to_allow(self):
        services = _build()
        services["threshold"].register(
            ExecutionPolicyRiskThreshold(
                threshold_id="threshold-1",
                level="HIGH",
                minimum_score=50,
                action="BLOCK",
            )
        )

        assert services["threshold"].evaluate("session-1") == "ALLOW"

    def test_block_action(self):
        services = _build()
        services["threshold"].register(
            ExecutionPolicyRiskThreshold(
                threshold_id="threshold-1",
                level="CRITICAL",
                minimum_score=75,
                action="BLOCK",
            )
        )
        _add_conflicts(services, "session-1", 3)

        assert services["threshold"].evaluate("session-1") == "BLOCK"

    def test_warn_action(self):
        services = _build()
        services["threshold"].register(
            ExecutionPolicyRiskThreshold(
                threshold_id="threshold-1",
                level="MEDIUM",
                minimum_score=25,
                action="WARN",
            )
        )
        services["threshold"].register(
            ExecutionPolicyRiskThreshold(
                threshold_id="threshold-2",
                level="CRITICAL",
                minimum_score=75,
                action="BLOCK",
            )
        )
        _add_conflicts(services, "session-1", 1)

        assert services["threshold"].evaluate("session-1") == "WARN"

    def test_disabled_threshold_is_ignored(self):
        services = _build()
        low = services["threshold"].register(
            ExecutionPolicyRiskThreshold(
                threshold_id="threshold-1",
                level="MEDIUM",
                minimum_score=0,
                action="BLOCK",
            )
        )
        services["threshold"].disable(low.threshold_id)

        assert services["threshold"].evaluate("session-1") == "ALLOW"

    def test_disable_unknown_threshold_is_an_error(self):
        services = _build()

        with pytest.raises(Error):
            services["threshold"].disable("unknown-threshold")

    def test_threshold_ordering_highest_wins(self):
        services = _build()
        services["threshold"].register(
            ExecutionPolicyRiskThreshold(
                threshold_id="threshold-low",
                level="LOW",
                minimum_score=0,
                action="ALLOW",
            )
        )
        services["threshold"].register(
            ExecutionPolicyRiskThreshold(
                threshold_id="threshold-medium",
                level="MEDIUM",
                minimum_score=25,
                action="WARN",
            )
        )
        services["threshold"].register(
            ExecutionPolicyRiskThreshold(
                threshold_id="threshold-critical",
                level="CRITICAL",
                minimum_score=75,
                action="BLOCK",
            )
        )
        _add_conflicts(services, "session-1", 3)

        assert services["threshold"].evaluate("session-1") == "BLOCK"
