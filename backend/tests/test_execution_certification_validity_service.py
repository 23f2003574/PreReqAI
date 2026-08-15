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
    ExecutionCertificationValidity,
    ExecutionCertificationValidityError as Error,
    ExecutionCertificationValidityService,
)


class _FakeCertificationService:
    def __init__(self, certifications_by_id):
        self._certifications_by_id = certifications_by_id

    def find(self, certification_id):
        return self._certifications_by_id.get(certification_id)


def _certification(certification_id, change_id="change-1", status="CERTIFIED", certified_at=None):
    return SimpleNamespace(
        certification_id=certification_id,
        change_id=change_id,
        status=status,
        certified_at=certified_at or datetime.now(timezone.utc),
    )


def _build(certifications_by_id, validity_period=timedelta(days=30)):
    certification_service = _FakeCertificationService(certifications_by_id)
    return ExecutionCertificationValidityService(certification_service, validity_period)


class TestExecutionCertificationValidityService:
    def test_active_certification(self):
        service = _build({"cert-1": _certification("cert-1")})

        record = service.check("cert-1")

        assert isinstance(record, ExecutionCertificationValidity)
        assert record.status == "ACTIVE"
        assert service.can_authorize("cert-1") is True

    def test_expiry(self):
        service = _build(
            {"cert-1": _certification("cert-1", certified_at=datetime.now(timezone.utc) - timedelta(days=31))},
            validity_period=timedelta(days=30),
        )

        record = service.check("cert-1")

        assert record.status == "EXPIRED"
        assert record.invalidated_at is not None

    def test_execution_blocked_after_expiry(self):
        service = _build(
            {"cert-1": _certification("cert-1", certified_at=datetime.now(timezone.utc) - timedelta(days=31))},
            validity_period=timedelta(days=30),
        )

        assert service.can_authorize("cert-1") is False

    def test_policy_change_invalidation(self):
        service = _build({"cert-1": _certification("cert-1")})

        record = service.invalidate("cert-1", "governing rule changed")

        assert record.status == "INVALIDATED"
        assert record.reason == "governing rule changed"
        assert service.can_authorize("cert-1") is False

    def test_manual_invalidation_requires_reason(self):
        service = _build({"cert-1": _certification("cert-1")})

        with pytest.raises(Error):
            service.invalidate("cert-1", "")

    def test_active_lookup(self):
        service = _build(
            {
                "cert-1": _certification("cert-1", change_id="change-1"),
                "cert-2": _certification("cert-2", change_id="change-1"),
                "cert-3": _certification("cert-3", change_id="change-2"),
            }
        )
        service.check("cert-1")
        service.check("cert-2")
        service.check("cert-3")
        service.invalidate("cert-2", "superseded")

        result = service.active("change-1")

        assert [record.certification_id for record in result] == ["cert-1"]

    def test_cannot_track_a_non_certified_record(self):
        service = _build({"cert-1": _certification("cert-1", status="FAILED")})

        with pytest.raises(Error):
            service.check("cert-1")

    def test_expire_terminal_record_is_an_error(self):
        service = _build({"cert-1": _certification("cert-1")})
        service.expire("cert-1")

        with pytest.raises(Error):
            service.expire("cert-1")
