from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionPolicyRiskOverride,
    ExecutionPolicyRiskOverrideError as Error,
    ExecutionPolicyRiskOverrideService,
)


def _future():
    return datetime.now(timezone.utc) + timedelta(hours=1)


def _past():
    return datetime.now(timezone.utc) - timedelta(seconds=1)


class TestExecutionPolicyRiskOverrideService:
    def test_create_and_validate(self):
        service = ExecutionPolicyRiskOverrideService()

        override = service.create("session-1", "HIGH", "known false positive", _future())

        assert isinstance(override, ExecutionPolicyRiskOverride)
        assert override.reason == "known false positive"
        assert service.validate(override.override_id) is True

    def test_validate_unknown_override_is_an_error(self):
        service = ExecutionPolicyRiskOverrideService()

        with pytest.raises(Error):
            service.validate("unknown-override")

    def test_active_lookup(self):
        service = ExecutionPolicyRiskOverrideService()

        override = service.create("session-1", "MEDIUM", "reason", _future())

        assert service.active("session-1") == [override]
        assert service.active("session-2") == []

    def test_expiry(self):
        service = ExecutionPolicyRiskOverrideService()

        override = service.create("session-1", "MEDIUM", "reason", _past())

        assert service.validate(override.override_id) is False
        assert service.active("session-1") == []
        assert service.expired() == [override]

    def test_revoke(self):
        service = ExecutionPolicyRiskOverrideService()

        override = service.create("session-1", "MEDIUM", "reason", _future())
        revoked = service.revoke(override.override_id)

        assert revoked.enabled is False
        assert service.validate(override.override_id) is False
        assert service.active("session-1") == []

    def test_revoke_unknown_override_is_an_error(self):
        service = ExecutionPolicyRiskOverrideService()

        with pytest.raises(Error):
            service.revoke("unknown-override")

    def test_excessive_level_rejection(self):
        service = ExecutionPolicyRiskOverrideService()

        with pytest.raises(Error):
            service.create("session-1", "CRITICAL", "reason", _future())

    def test_missing_reason_rejection(self):
        service = ExecutionPolicyRiskOverrideService()

        with pytest.raises(Error):
            service.create("session-1", "MEDIUM", "", _future())

    def test_missing_expiry_rejection(self):
        service = ExecutionPolicyRiskOverrideService()

        with pytest.raises(Error):
            service.create("session-1", "MEDIUM", "reason", None)

    def test_reason_is_retained_after_expiry_and_revocation(self):
        service = ExecutionPolicyRiskOverrideService()

        service.create("session-1", "MEDIUM", "temporary tolerance", _past())
        revoked = service.create("session-1", "MEDIUM", "temporary tolerance", _future())
        revoked_record = service.revoke(revoked.override_id)

        assert service.expired()[0].reason == "temporary tolerance"
        assert revoked_record.reason == "temporary tolerance"
