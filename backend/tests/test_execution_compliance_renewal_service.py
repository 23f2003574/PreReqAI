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
    ExecutionComplianceRenewal,
    ExecutionComplianceRenewalError as Error,
    ExecutionComplianceRenewalService,
)


class _FakeValidityService:
    def __init__(self, status_by_certification, expires_at):
        self._status_by_certification = status_by_certification
        self._expires_at = expires_at

    def check(self, certification_id):
        status = self._status_by_certification.get(certification_id)

        if status is None:
            raise ValueError(f"unknown certification {certification_id!r}")

        return SimpleNamespace(certification_id=certification_id, status=status, expires_at=self._expires_at)


def _build(status_by_certification, expires_at=None, authorized_reviewers=("reviewer-1",)):
    validity_service = _FakeValidityService(
        status_by_certification,
        expires_at or datetime.now(timezone.utc) + timedelta(days=10),
    )
    return ExecutionComplianceRenewalService(validity_service, authorized_reviewers)


class TestExecutionComplianceRenewalService:
    def test_successful_renewal(self):
        expires_at = datetime.now(timezone.utc) + timedelta(days=10)
        service = _build({"cert-1": "ACTIVE"}, expires_at=expires_at)
        new_expiry = expires_at + timedelta(days=30)

        renewal = service.renew("cert-1", "reviewer-1", new_expiry)

        assert isinstance(renewal, ExecutionComplianceRenewal)
        assert renewal.previous_expiry == expires_at
        assert renewal.new_expiry == new_expiry

    def test_expired_certification_rejected(self):
        service = _build({"cert-1": "EXPIRED"})

        with pytest.raises(Error):
            service.renew("cert-1", "reviewer-1", datetime.now(timezone.utc) + timedelta(days=30))

    def test_revoked_certification_rejected(self):
        service = _build({"cert-1": "INVALIDATED"})

        with pytest.raises(Error):
            service.renew("cert-1", "reviewer-1", datetime.now(timezone.utc) + timedelta(days=30))

    def test_invalid_expiry_rejected(self):
        expires_at = datetime.now(timezone.utc) + timedelta(days=10)
        service = _build({"cert-1": "ACTIVE"}, expires_at=expires_at)

        with pytest.raises(Error):
            service.renew("cert-1", "reviewer-1", expires_at - timedelta(days=1))

    def test_reviewer_authorization_required(self):
        service = _build({"cert-1": "ACTIVE"})

        with pytest.raises(Error):
            service.renew("cert-1", "intruder", datetime.now(timezone.utc) + timedelta(days=30))

    def test_renewal_history(self):
        expires_at = datetime.now(timezone.utc) + timedelta(days=10)
        service = _build({"cert-1": "ACTIVE"}, expires_at=expires_at)

        first = service.renew("cert-1", "reviewer-1", expires_at + timedelta(days=30))
        second = service.renew("cert-1", "reviewer-1", expires_at + timedelta(days=60))

        assert service.history("cert-1") == (first, second)
        assert service.eligible("cert-1") is True
