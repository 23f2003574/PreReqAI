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
    ExecutionApprovalDelegation,
    ExecutionApprovalDelegationError as Error,
    ExecutionApprovalDelegationService,
)


class _FakeApprovalRequestService:
    def __init__(self, actions_by_request):
        self._actions_by_request = actions_by_request

    def find(self, request_id):
        action = self._actions_by_request.get(request_id)

        if action is None:
            return None

        return SimpleNamespace(request_id=request_id, action=action)


def _build(actions_by_request=None):
    request_service = _FakeApprovalRequestService(actions_by_request or {})
    return ExecutionApprovalDelegationService(request_service)


def _future(hours=1):
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def _past(hours=1):
    return datetime.now(timezone.utc) - timedelta(hours=hours)


class TestExecutionApprovalDelegationService:
    def test_create_delegation(self):
        service = _build()

        delegation = service.delegate("approver-1", "delegate-1", "delete_dataset", _future())

        assert isinstance(delegation, ExecutionApprovalDelegation)
        assert delegation.approver == "approver-1"
        assert delegation.delegate == "delegate-1"
        assert delegation.enabled is True

    def test_delegation_requires_expiry(self):
        service = _build()

        with pytest.raises(Error):
            service.delegate("approver-1", "delegate-1", "delete_dataset", None)

    def test_authorized_approval(self):
        service = _build(actions_by_request={"request-1": "delete_dataset"})
        delegation = service.delegate("approver-1", "delegate-1", "delete_dataset", _future())

        authorized = service.authorize("delegate-1", "request-1")

        assert authorized == delegation

    def test_scope_mismatch_is_rejected(self):
        service = _build(actions_by_request={"request-1": "export_data"})
        service.delegate("approver-1", "delegate-1", "delete_dataset", _future())

        with pytest.raises(Error):
            service.authorize("delegate-1", "request-1")

    def test_expired_delegation_is_rejected(self):
        service = _build(actions_by_request={"request-1": "delete_dataset"})
        service.delegate("approver-1", "delegate-1", "delete_dataset", _future(hours=-1))

        with pytest.raises(Error):
            service.authorize("delegate-1", "request-1")

    def test_revoked_delegation_is_rejected(self):
        service = _build(actions_by_request={"request-1": "delete_dataset"})
        delegation = service.delegate("approver-1", "delegate-1", "delete_dataset", _future())

        service.revoke(delegation.delegation_id)

        with pytest.raises(Error):
            service.authorize("delegate-1", "request-1")

    def test_active_lookup(self):
        service = _build()
        active = service.delegate("approver-1", "delegate-1", "delete_dataset", _future())
        expiring = service.delegate("approver-1", "delegate-2", "export_data", _future())
        service.revoke(expiring.delegation_id)

        result = service.active("approver-1")

        assert result == [active]
