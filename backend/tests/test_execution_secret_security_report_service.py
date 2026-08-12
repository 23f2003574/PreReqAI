import pytest

from backend.session import (
    ExecutionSecretAccessService,
    ExecutionSecretAnomalyService,
    ExecutionSecretAuditEvent,
    ExecutionSecretAuditOperation as AuditOperation,
    ExecutionSecretAuditService,
    ExecutionSecretLeaseService,
    ExecutionSecretOperation as Operation,
    ExecutionSecretPostureLevel as Level,
    ExecutionSecretReportError as Error,
    ExecutionSecretRevocationService,
    ExecutionSecretRotationService,
    ExecutionSecretSecurityPolicy,
    ExecutionSecretSecurityPolicyService,
    ExecutionSecretSecurityPosture,
    ExecutionSecretSecurityPostureService,
    ExecutionSecretSecurityReport,
    ExecutionSecretSecurityReportService,
    ExecutionSecretService,
    ExecutionSecretTrustLevel as TrustLevel,
    ExecutionSecretTrustPolicy,
    ExecutionSecretTrustService,
)


def _build():
    secret_service = ExecutionSecretService()
    access_service = ExecutionSecretAccessService()
    trust_service = ExecutionSecretTrustService()
    lease_service = ExecutionSecretLeaseService(access_service)
    rotation_service = ExecutionSecretRotationService(secret_service)
    revocation_service = ExecutionSecretRevocationService(lease_service)
    audit_service = ExecutionSecretAuditService()
    anomaly_service = ExecutionSecretAnomalyService(audit_service, lease_service, revocation_service)
    posture_service = ExecutionSecretSecurityPostureService(
        access_service, trust_service, lease_service, rotation_service, revocation_service, audit_service
    )
    policy_service = ExecutionSecretSecurityPolicyService(
        rotation_service, lease_service, trust_service, access_service, audit_service
    )
    report_service = ExecutionSecretSecurityReportService(
        posture_service, policy_service, anomaly_service, audit_service
    )
    return {
        "secret": secret_service,
        "access": access_service,
        "trust": trust_service,
        "lease": lease_service,
        "rotation": rotation_service,
        "revocation": revocation_service,
        "audit": audit_service,
        "anomaly": anomaly_service,
        "posture": posture_service,
        "policy": policy_service,
        "report": report_service,
    }


def _grant_and_trust(services, secret_id="secret-1", principal="component-a"):
    services["access"].grant(secret_id, principal, {Operation.READ})
    services["trust"].register(
        ExecutionSecretTrustPolicy(
            policy_id=f"trust-{secret_id}-{principal}",
            principal=principal,
            trust_level=TrustLevel.STANDARD,
            allowed_operations=frozenset(),
        )
    )


def _record_access(services, secret_id="secret-1", session_id="session-1", principal="component-a"):
    services["audit"].record(
        ExecutionSecretAuditEvent(
            secret_id=secret_id,
            session_id=session_id,
            principal=principal,
            operation=AuditOperation.ACCESS,
        )
    )


class TestExecutionSecretSecurityReportService:
    def test_generate_report(self):
        services = _build()
        _grant_and_trust(services)
        services["rotation"].rotate("secret-1")

        report = services["report"].generate("secret-1")

        assert isinstance(report, ExecutionSecretSecurityReport)
        assert report.secret_id == "secret-1"
        assert isinstance(report.posture, ExecutionSecretSecurityPosture)

    def test_posture_inclusion(self):
        services = _build()
        _grant_and_trust(services)
        services["rotation"].rotate("secret-1")

        report = services["report"].generate("secret-1")
        expected_posture = services["posture"].evaluate("secret-1")

        assert report.posture.level == expected_posture.level
        assert report.posture.violations == expected_posture.violations

    def test_violation_inclusion(self):
        services = _build()
        services["policy"].register(
            ExecutionSecretSecurityPolicy(policy_id="policy-1", secret_id="secret-1", require_rotation=True)
        )

        report = services["report"].generate("secret-1")

        assert "missing_rotation" in report.violations

    def test_anomaly_inclusion(self):
        services = _build()
        services["revocation"].revoke("secret-1", "compromised credential")
        _record_access(services)
        services["anomaly"].detect("secret-1")

        report = services["report"].generate("secret-1")

        assert "anomaly:revoked_access:component-a" in report.violations

    def test_audit_summary_inclusion(self):
        services = _build()
        _record_access(services)
        _record_access(services)

        report = services["report"].generate("secret-1")

        assert report.audit_summary["total_events"] == 2
        assert report.audit_summary["operation_counts"]["access"] == 2
        assert report.audit_summary["last_event_at"] is not None

    def test_report_history(self):
        services = _build()

        first = services["report"].generate("secret-1")
        second = services["report"].generate("secret-1")

        assert services["report"].history("secret-1") == [first, second]

    def test_get_report(self):
        services = _build()
        report = services["report"].generate("secret-1")

        assert services["report"].get(report.report_id) == report

        with pytest.raises(Error):
            services["report"].get("unknown-report")

    def test_deterministic_output(self):
        services = _build()
        _grant_and_trust(services)
        services["rotation"].rotate("secret-1")

        first = services["report"].generate("secret-1")
        second = services["report"].generate("secret-1")

        assert first.posture.level == second.posture.level
        assert first.posture.violations == second.posture.violations
        assert first.violations == second.violations
        assert first.audit_summary == second.audit_summary
        assert first.report_id != second.report_id

    def test_report_comparison(self):
        services = _build()
        _grant_and_trust(services)
        services["policy"].register(
            ExecutionSecretSecurityPolicy(policy_id="policy-1", secret_id="secret-1", require_rotation=True)
        )
        before = services["report"].generate("secret-1")

        services["rotation"].rotate("secret-1")
        after = services["report"].generate("secret-1")

        comparison = services["report"].compare(before, after)

        assert comparison["secret_id"] == "secret-1"
        assert comparison["previous_level"] == Level.DEGRADED
        assert comparison["current_level"] == Level.SECURE
        assert comparison["level_changed"] is True
        assert comparison["violations_removed"] == ["missing_rotation"]
        assert comparison["violations_added"] == []

    def test_compare_rejects_different_secrets(self):
        services = _build()
        report_a = services["report"].generate("secret-1")
        report_b = services["report"].generate("secret-2")

        with pytest.raises(Error):
            services["report"].compare(report_a, report_b)

    def test_rejects_invalid_arguments(self):
        services = _build()

        with pytest.raises(Error):
            services["report"].generate("")

        with pytest.raises(Error):
            services["report"].get("")

        with pytest.raises(Error):
            services["report"].history("")

        with pytest.raises(Error):
            services["report"].compare("not-a-report", "also-not-a-report")
