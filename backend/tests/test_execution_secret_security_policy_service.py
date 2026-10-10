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
    ExecutionSecretRotationService,
    ExecutionSecretSecurityPolicy,
    ExecutionSecretSecurityPolicyError as Error,
    ExecutionSecretSecurityPolicyService,
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
    audit_service = ExecutionSecretAuditService()
    policy_service = ExecutionSecretSecurityPolicyService(
        rotation_service,
        lease_service,
        trust_service,
        access_service,
        audit_service,
    )
    return access_service, trust_service, lease_service, rotation_service, audit_service, policy_service


def _grant_and_trust(access_service, trust_service, secret_id="secret-1", principal="component-a"):
    access_service.grant(secret_id, principal, {Operation.READ})
    trust_service.register(
        ExecutionSecretTrustPolicy(
            policy_id=f"trust-{secret_id}-{principal}",
            principal=principal,
            trust_level=TrustLevel.STANDARD,
            allowed_operations=frozenset(),
        )
    )


class TestExecutionSecretSecurityPolicyService:
    def test_compliant_secret(self):
        access_service, trust_service, lease_service, rotation_service, audit_service, policy_service = _build()
        _grant_and_trust(access_service, trust_service)
        rotation_service.rotate("secret-1")
        lease_service.acquire("secret-1", "component-a")
        audit_service.record(
            ExecutionSecretAuditEvent(
                secret_id="secret-1",
                session_id="session-1",
                principal="component-a",
                operation=AuditOperation.ACCESS,
            )
        )
        policy_service.register(
            ExecutionSecretSecurityPolicy(
                policy_id="policy-1",
                secret_id="secret-1",
                require_rotation=True,
                require_lease=True,
                require_trust=True,
                require_audit=True,
            )
        )

        assert policy_service.validate("secret-1") is True
        assert policy_service.violations("secret-1") == []

    def test_missing_rotation(self):
        access_service, trust_service, _lease, _rotation, _audit, policy_service = _build()
        _grant_and_trust(access_service, trust_service)
        policy_service.register(
            ExecutionSecretSecurityPolicy(policy_id="policy-1", secret_id="secret-1", require_rotation=True)
        )

        assert policy_service.validate("secret-1") is False
        assert policy_service.violations("secret-1") == ["missing_rotation"]

    def test_missing_lease(self):
        access_service, trust_service, _lease, _rotation, _audit, policy_service = _build()
        _grant_and_trust(access_service, trust_service)
        policy_service.register(
            ExecutionSecretSecurityPolicy(policy_id="policy-1", secret_id="secret-1", require_lease=True)
        )

        assert policy_service.validate("secret-1") is False
        assert policy_service.violations("secret-1") == ["missing_lease"]

    def test_missing_trust(self):
        _access, _trust, _lease, _rotation, _audit, policy_service = _build()
        policy_service.register(
            ExecutionSecretSecurityPolicy(policy_id="policy-1", secret_id="secret-1", require_trust=True)
        )

        assert policy_service.validate("secret-1") is False
        assert policy_service.violations("secret-1") == ["missing_trust"]

    def test_missing_audit(self):
        access_service, trust_service, _lease, _rotation, _audit, policy_service = _build()
        _grant_and_trust(access_service, trust_service)
        policy_service.register(
            ExecutionSecretSecurityPolicy(policy_id="policy-1", secret_id="secret-1", require_audit=True)
        )

        assert policy_service.validate("secret-1") is False
        assert policy_service.violations("secret-1") == ["missing_audit"]

    def test_multiple_violations(self):
        _access, _trust, _lease, _rotation, _audit, policy_service = _build()
        policy_service.register(
            ExecutionSecretSecurityPolicy(
                policy_id="policy-1",
                secret_id="secret-1",
                require_rotation=True,
                require_lease=True,
                require_trust=True,
                require_audit=True,
            )
        )

        assert policy_service.validate("secret-1") is False
        assert policy_service.violations("secret-1") == [
            "missing_rotation",
            "missing_lease",
            "missing_trust",
            "missing_audit",
        ]

    def test_disabled_policy(self):
        _access, _trust, _lease, _rotation, _audit, policy_service = _build()
        policy_service.register(
            ExecutionSecretSecurityPolicy(policy_id="policy-1", secret_id="secret-1", require_rotation=True)
        )

        disabled = policy_service.disable("policy-1")

        assert disabled.enabled is False
        assert policy_service.validate("secret-1") is True
        assert policy_service.violations("secret-1") == []

    def test_disable_rejects_unknown_policy(self):
        _access, _trust, _lease, _rotation, _audit, policy_service = _build()

        with pytest.raises(Error):
            policy_service.disable("unknown-policy")

    def test_secret_with_no_policy_is_compliant(self):
        _access, _trust, _lease, _rotation, _audit, policy_service = _build()

        assert policy_service.validate("secret-1") is True
        assert policy_service.violations("secret-1") == []

    def test_requirements_are_additive_across_policies(self):
        access_service, trust_service, lease_service, rotation_service, _audit, policy_service = _build()
        _grant_and_trust(access_service, trust_service)
        rotation_service.rotate("secret-1")
        policy_service.register(
            ExecutionSecretSecurityPolicy(policy_id="policy-1", secret_id="secret-1", require_rotation=True)
        )
        policy_service.register(
            ExecutionSecretSecurityPolicy(policy_id="policy-2", secret_id="secret-1", require_lease=True)
        )

        assert policy_service.violations("secret-1") == ["missing_lease"]

    def test_rejects_duplicate_policy_id(self):
        _access, _trust, _lease, _rotation, _audit, policy_service = _build()
        policy_service.register(
            ExecutionSecretSecurityPolicy(policy_id="policy-1", secret_id="secret-1", require_rotation=True)
        )

        with pytest.raises(Error):
            policy_service.register(
                ExecutionSecretSecurityPolicy(policy_id="policy-1", secret_id="secret-2", require_lease=True)
            )

    def test_rejects_invalid_arguments(self):
        _access, _trust, _lease, _rotation, _audit, policy_service = _build()

        with pytest.raises(Error):
            policy_service.validate("")

        with pytest.raises(Error):
            policy_service.violations("")

        with pytest.raises(Error):
            policy_service.disable("")

        with pytest.raises(Error):
            policy_service.register("not-a-policy")
