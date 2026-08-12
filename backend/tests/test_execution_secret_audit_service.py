import pytest

from backend.session import (
    ExecutionSecretAuditError as Error,
    ExecutionSecretAuditEvent,
    ExecutionSecretAuditOperation as Operation,
    ExecutionSecretAuditService,
)


def _event(secret_id="secret-1", session_id="session-1", principal="component-a", operation=Operation.ACCESS, **kwargs):
    return ExecutionSecretAuditEvent(
        secret_id=secret_id,
        session_id=session_id,
        principal=principal,
        operation=operation,
        **kwargs,
    )


class TestExecutionSecretAuditService:
    def test_record_event(self):
        audit_service = ExecutionSecretAuditService()

        recorded = audit_service.record(_event())

        assert isinstance(recorded, ExecutionSecretAuditEvent)
        assert recorded.operation == Operation.ACCESS

    def test_secret_history(self):
        audit_service = ExecutionSecretAuditService()

        first = audit_service.record(_event(operation=Operation.LEASE))
        second = audit_service.record(_event(operation=Operation.ROTATION))
        audit_service.record(_event(secret_id="secret-2", operation=Operation.ACCESS))

        assert audit_service.history("secret-1") == [first, second]

    def test_session_filtering(self):
        audit_service = ExecutionSecretAuditService()

        first = audit_service.record(_event(session_id="session-1"))
        second = audit_service.record(_event(session_id="session-1", secret_id="secret-2"))
        audit_service.record(_event(session_id="session-2"))

        assert audit_service.session_history("session-1") == [first, second]

    def test_principal_filtering(self):
        audit_service = ExecutionSecretAuditService()

        first = audit_service.record(_event(principal="component-a"))
        second = audit_service.record(_event(principal="component-a", secret_id="secret-2"))
        audit_service.record(_event(principal="component-b"))

        assert audit_service.principal_history("component-a") == [first, second]

    def test_latest_event(self):
        audit_service = ExecutionSecretAuditService()

        audit_service.record(_event(operation=Operation.LEASE))
        latest = audit_service.record(_event(operation=Operation.REVOCATION))

        assert audit_service.latest("secret-1") == latest

    def test_latest_requires_recorded_history(self):
        audit_service = ExecutionSecretAuditService()

        with pytest.raises(Error):
            audit_service.latest("secret-1")

    def test_raw_value_exclusion(self):
        with pytest.raises(Error):
            _event(metadata={"value": "supersecret"})

        with pytest.raises(Error):
            _event(metadata={"raw_value": "supersecret"})

        # A reference or other non-raw detail is fine.
        event = _event(metadata={"value_ref": "vault://api-key", "reason": "scheduled rotation"})
        assert event.metadata["value_ref"] == "vault://api-key"

    def test_append_only_rejects_duplicate_event_id(self):
        audit_service = ExecutionSecretAuditService()
        event = _event()
        audit_service.record(event)

        with pytest.raises(Error):
            audit_service.record(event)

    def test_rejects_invalid_arguments(self):
        audit_service = ExecutionSecretAuditService()

        with pytest.raises(Error):
            audit_service.record("not-an-event")

        with pytest.raises(Error):
            audit_service.history("")

        with pytest.raises(Error):
            audit_service.session_history("")

        with pytest.raises(Error):
            audit_service.principal_history("")
