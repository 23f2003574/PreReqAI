from datetime import (
    datetime,
    timedelta,
    timezone,
)

from types import (
    SimpleNamespace,
)

import pytest

from backend.session import (
    ExecutionComplianceException,
    ExecutionComplianceExceptionError as Error,
    ExecutionComplianceExceptionService,
)


class _FakeComplianceService:
    def __init__(self, severities_by_rule):
        self._severities_by_rule = severities_by_rule

    def find(self, rule_id):
        severity = self._severities_by_rule.get(rule_id)

        if severity is None:
            return None

        return SimpleNamespace(rule_id=rule_id, severity=severity)


def _build(severities_by_rule=None):
    compliance_service = _FakeComplianceService(severities_by_rule or {})
    return ExecutionComplianceExceptionService(compliance_service)


def _future(hours=1):
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _past(hours=1):
    return datetime.now(timezone.utc) - timedelta(hours=hours)


class TestExecutionComplianceExceptionService:
    def test_create_and_validate(self):
        service = _build({"rule-1": "BLOCKING"})

        exception = service.create("rule-1", "change-1", "urgent fix", "approver-1", _future())

        assert isinstance(exception, ExecutionComplianceException)
        assert service.validate(exception.exception_id) is True

    def test_blocking_rule_override_required(self):
        service = _build({"rule-1": "WARNING"})

        with pytest.raises(Error):
            service.create("rule-1", "change-1", "urgent fix", "approver-1", _future())

    def test_unknown_rule_is_an_error(self):
        service = _build()

        with pytest.raises(Error):
            service.create("unknown-rule", "change-1", "urgent fix", "approver-1", _future())

    def test_missing_approver_is_an_error(self):
        service = _build({"rule-1": "BLOCKING"})

        with pytest.raises(Error):
            service.create("rule-1", "change-1", "urgent fix", "", _future())

    def test_expiry_is_mandatory(self):
        service = _build({"rule-1": "BLOCKING"})

        with pytest.raises(Error):
            service.create("rule-1", "change-1", "urgent fix", "approver-1", None)

    def test_expired_exception_cannot_bypass_violation(self):
        service = _build({"rule-1": "BLOCKING"})
        exception = service.create("rule-1", "change-1", "urgent fix", "approver-1", _past())

        assert service.validate(exception.exception_id) is False
        assert service.active("change-1") == []

    def test_revocation(self):
        service = _build({"rule-1": "BLOCKING"})
        exception = service.create("rule-1", "change-1", "urgent fix", "approver-1", _future())

        revoked = service.revoke(exception.exception_id)

        assert revoked.enabled is False
        assert service.validate(exception.exception_id) is False

    def test_active_lookup(self):
        service = _build({"rule-1": "BLOCKING", "rule-2": "BLOCKING"})
        active = service.create("rule-1", "change-1", "urgent fix", "approver-1", _future())
        revoked = service.create("rule-2", "change-1", "urgent fix", "approver-1", _future())
        service.revoke(revoked.exception_id)

        assert service.active("change-1") == [active]
