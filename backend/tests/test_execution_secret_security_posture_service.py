from datetime import (
    timedelta,
)

import pytest

from backend.session import (
    ExecutionSecretAccessService,
    ExecutionSecretAuditEvent,
    ExecutionSecretAuditOperation as AuditOperation,
    ExecutionSecretAuditService,
    ExecutionSecretLeaseService,
    ExecutionSecretOperation as Operation,
    ExecutionSecretPostureError as Error,
    ExecutionSecretPostureLevel as Level,
    ExecutionSecretRevocationService,
    ExecutionSecretRotationService,
    ExecutionSecretSecurityPosture,
    ExecutionSecretSecurityPostureService,
    ExecutionSecretService,
    ExecutionSecretTrustLevel as TrustLevel,
    ExecutionSecretTrustPolicy,
    ExecutionSecretTrustService,
)


def _build(lease_ttl=timedelta(minutes=15)):
    secret_service = ExecutionSecretService()
    access_service = ExecutionSecretAccessService()
    trust_service = ExecutionSecretTrustService()
    lease_service = ExecutionSecretLeaseService(access_service, ttl=lease_ttl)
    rotation_service = ExecutionSecretRotationService(secret_service)
    revocation_service = ExecutionSecretRevocationService(lease_service)
    audit_service = ExecutionSecretAuditService()
    posture_service = ExecutionSecretSecurityPostureService(
        access_service,
        trust_service,
        lease_service,
        rotation_service,
        revocation_service,
        audit_service,
    )
    return (
        secret_service,
        access_service,
        trust_service,
        lease_service,
        rotation_service,
        revocation_service,
        audit_service,
        posture_service,
    )


def _trust(trust_service, principal, level=TrustLevel.STANDARD):
    trust_service.register(
        ExecutionSecretTrustPolicy(
            policy_id=f"trust-{principal}",
            principal=principal,
            trust_level=level,
            allowed_operations=frozenset(),
        )
    )


class TestExecutionSecretSecurityPostureService:
    def test_secure_posture(self):
        _s, access_service, trust_service, _l, rotation_service, _r, _a, posture_service = _build()
        access_service.grant("secret-1", "component-a", {Operation.READ})
        _trust(trust_service, "component-a")
        rotation_service.rotate("secret-1")

        posture = posture_service.evaluate("secret-1")

        assert isinstance(posture, ExecutionSecretSecurityPosture)
        assert posture.level == Level.SECURE
        assert posture.violations == ()

    def test_degraded_posture_never_rotated(self):
        _s, access_service, trust_service, _l, _rot, _r, _a, posture_service = _build()
        access_service.grant("secret-1", "component-a", {Operation.READ})
        _trust(trust_service, "component-a")

        posture = posture_service.evaluate("secret-1")

        assert posture.level == Level.DEGRADED
        assert posture.violations == ("never_rotated",)

    def test_degraded_posture_low_trust_principal(self):
        _s, access_service, _trust_service, _l, rotation_service, _r, _a, posture_service = _build()
        access_service.grant("secret-1", "component-a", {Operation.READ})
        rotation_service.rotate("secret-1")

        posture = posture_service.evaluate("secret-1")

        assert posture.level == Level.DEGRADED
        assert posture.violations == ("low_trust_principal:component-a",)

    def test_degraded_posture_uncleaned_expired_lease(self):
        _s, access_service, trust_service, lease_service, rotation_service, _r, _a, posture_service = _build(
            lease_ttl=timedelta(seconds=-1)
        )
        access_service.grant("secret-1", "component-a", {Operation.READ})
        _trust(trust_service, "component-a")
        rotation_service.rotate("secret-1")
        lease_service.acquire("secret-1", "component-a")

        posture = posture_service.evaluate("secret-1")

        assert posture.level == Level.DEGRADED
        assert posture.violations == ("uncleaned_expired_lease",)

    def test_revoked_posture(self):
        _s, access_service, trust_service, _l, rotation_service, revocation_service, _a, posture_service = _build()
        access_service.grant("secret-1", "component-a", {Operation.READ})
        _trust(trust_service, "component-a")
        rotation_service.rotate("secret-1")
        revocation_service.revoke("secret-1", "compromised credential")

        posture = posture_service.evaluate("secret-1")

        assert posture.level == Level.COMPROMISED
        assert posture.violations == ("secret_revoked",)

    def test_revocation_overrides_an_otherwise_degraded_posture(self):
        _s, _access, _trust_service, _l, _rot, revocation_service, _a, posture_service = _build()
        revocation_service.revoke("secret-1", "compromised credential")

        posture = posture_service.evaluate("secret-1")

        assert posture.level == Level.COMPROMISED
        assert "no_access_policy" in posture.violations
        assert "never_rotated" in posture.violations
        assert "secret_revoked" in posture.violations

    def test_multiple_violations(self):
        _s, _access, _trust_service, _l, _rot, _r, _a, posture_service = _build()

        posture = posture_service.evaluate("secret-1")

        assert posture.level == Level.DEGRADED
        assert posture.violations == ("no_access_policy", "never_rotated")

    def test_session_evaluation(self):
        (
            _s,
            access_service,
            trust_service,
            _l,
            rotation_service,
            _r,
            audit_service,
            posture_service,
        ) = _build()
        access_service.grant("secret-1", "component-a", {Operation.READ})
        _trust(trust_service, "component-a")
        rotation_service.rotate("secret-1")
        audit_service.record(
            ExecutionSecretAuditEvent(
                secret_id="secret-1",
                session_id="session-1",
                principal="component-a",
                operation=AuditOperation.ACCESS,
            )
        )
        audit_service.record(
            ExecutionSecretAuditEvent(
                secret_id="secret-2",
                session_id="session-1",
                principal="component-a",
                operation=AuditOperation.ACCESS,
            )
        )

        postures = posture_service.evaluate_session("session-1")

        assert [posture.secret_id for posture in postures] == ["secret-1", "secret-2"]
        assert postures[0].level == Level.SECURE
        assert postures[1].level == Level.DEGRADED

    def test_deterministic_results(self):
        _s, access_service, trust_service, _l, rotation_service, _r, _a, posture_service = _build()
        access_service.grant("secret-1", "component-a", {Operation.READ})
        _trust(trust_service, "component-a")
        rotation_service.rotate("secret-1")

        first = posture_service.evaluate("secret-1")
        second = posture_service.evaluate("secret-1")

        assert first.level == second.level
        assert first.violations == second.violations

    def test_violations_lookup(self):
        _s, _access, _trust_service, _l, _rot, _r, _a, posture_service = _build()

        assert posture_service.violations("secret-1") == ["no_access_policy", "never_rotated"]

    def test_rejects_invalid_arguments(self):
        _s, _access, _trust_service, _l, _rot, _r, _a, posture_service = _build()

        with pytest.raises(Error):
            posture_service.evaluate("")

        with pytest.raises(Error):
            posture_service.evaluate_session("")

        with pytest.raises(Error):
            posture_service.violations("")
