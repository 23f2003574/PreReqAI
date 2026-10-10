from datetime import (
    timedelta,
)

import pytest

from backend.session import (
    ExecutionSecretAccessService,
    ExecutionSecretAnomaly,
    ExecutionSecretAnomalyError as Error,
    ExecutionSecretAnomalyService,
    ExecutionSecretAnomalyType as AnomalyType,
    ExecutionSecretAuditEvent,
    ExecutionSecretAuditOperation as AuditOperation,
    ExecutionSecretAuditService,
    ExecutionSecretLeaseService,
    ExecutionSecretOperation as Operation,
    ExecutionSecretRevocationService,
)


def _build(lease_ttl=timedelta(minutes=15)):
    access_service = ExecutionSecretAccessService()
    audit_service = ExecutionSecretAuditService()
    lease_service = ExecutionSecretLeaseService(access_service, ttl=lease_ttl)
    revocation_service = ExecutionSecretRevocationService(lease_service)
    anomaly_service = ExecutionSecretAnomalyService(audit_service, lease_service, revocation_service)
    return access_service, audit_service, lease_service, revocation_service, anomaly_service


def _access_event(secret_id="secret-1", session_id="session-1", principal="component-a", **metadata):
    return ExecutionSecretAuditEvent(
        secret_id=secret_id,
        session_id=session_id,
        principal=principal,
        operation=AuditOperation.ACCESS,
        metadata=metadata,
    )


class TestExecutionSecretAnomalyService:
    def test_revoked_access_detection(self):
        _access_service, audit_service, _lease_service, revocation_service, anomaly_service = _build()
        revocation_service.revoke("secret-1", "compromised credential")
        audit_service.record(_access_event(outcome="granted"))

        anomalies = anomaly_service.detect("secret-1")

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.REVOKED_ACCESS
        assert anomalies[0].secret_id == "secret-1"
        assert anomalies[0].principal == "component-a"

    def test_repeated_denial_detection(self):
        _access_service, audit_service, _lease_service, _revocation_service, anomaly_service = _build()

        for _ in range(3):
            audit_service.record(_access_event(outcome="denied"))

        anomalies = anomaly_service.detect("secret-1")

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.REPEATED_DENIAL
        assert anomalies[0].details["denied_count"] == 3

        # A further denial does not re-flag the same principal.
        audit_service.record(_access_event(outcome="denied"))
        assert anomaly_service.detect("secret-1") == []

    def test_expired_lease_detection(self):
        access_service, audit_service, lease_service, _revocation_service, anomaly_service = _build(
            lease_ttl=timedelta(seconds=-1)
        )
        access_service.grant("secret-1", "component-a", {Operation.READ})
        lease = lease_service.acquire("secret-1", "component-a")
        audit_service.record(_access_event(outcome="granted", lease_id=lease.lease_id))

        anomalies = anomaly_service.detect("secret-1")

        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == AnomalyType.EXPIRED_LEASE_ACCESS
        assert anomalies[0].details["lease_id"] == lease.lease_id

    def test_anomaly_listing(self):
        _access_service, audit_service, _lease_service, revocation_service, anomaly_service = _build()
        revocation_service.revoke("secret-1", "compromised credential")
        audit_service.record(_access_event())

        detected = anomaly_service.detect("secret-1")

        assert anomaly_service.active() == detected

        # Calling detect() again does not duplicate the same evidence.
        assert anomaly_service.detect("secret-1") == []
        assert anomaly_service.active() == detected

    def test_resolution(self):
        _access_service, audit_service, _lease_service, revocation_service, anomaly_service = _build()
        revocation_service.revoke("secret-1", "compromised credential")
        audit_service.record(_access_event())
        [anomaly] = anomaly_service.detect("secret-1")

        resolved = anomaly_service.resolve(anomaly.anomaly_id)

        assert isinstance(resolved, ExecutionSecretAnomaly)
        assert resolved.anomaly_id == anomaly.anomaly_id
        assert anomaly_service.active() == []

        with pytest.raises(Error):
            anomaly_service.resolve(anomaly.anomaly_id)

    def test_false_positive_isolation(self):
        access_service, audit_service, lease_service, _revocation_service, anomaly_service = _build()
        access_service.grant("secret-1", "component-a", {Operation.READ})
        lease = lease_service.acquire("secret-1", "component-a")
        audit_service.record(_access_event(outcome="granted", lease_id=lease.lease_id))
        audit_service.record(_access_event(outcome="granted", lease_id=lease.lease_id))

        assert anomaly_service.detect("secret-1") == []
        assert anomaly_service.active() == []

    def test_detect_session(self):
        _access_service, audit_service, _lease_service, revocation_service, anomaly_service = _build()
        revocation_service.revoke("secret-1", "compromised credential")
        audit_service.record(_access_event(secret_id="secret-1", session_id="session-1"))
        audit_service.record(_access_event(secret_id="secret-2", session_id="session-1"))

        detected = anomaly_service.detect_session("session-1")

        assert len(detected) == 1
        assert detected[0].secret_id == "secret-1"

    def test_rejects_invalid_arguments(self):
        _access_service, _audit_service, _lease_service, _revocation_service, anomaly_service = _build()

        with pytest.raises(Error):
            anomaly_service.detect("")

        with pytest.raises(Error):
            anomaly_service.detect_session("")

        with pytest.raises(Error):
            anomaly_service.resolve("")

        with pytest.raises(Error):
            anomaly_service.resolve("unknown-anomaly")
