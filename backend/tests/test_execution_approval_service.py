import pytest

from backend.session import (
    ExecutionApprovalError as Error,
    ExecutionApprovalRequest,
    ExecutionApprovalService,
)


def _build():
    return ExecutionApprovalService()


class TestExecutionApprovalService:
    def test_create_and_approve(self):
        service = _build()

        request = service.create("session-1", "delete_dataset", "researcher-1")

        assert isinstance(request, ExecutionApprovalRequest)
        assert request.status == "PENDING"
        assert request.approver is None

        approved = service.approve(request.request_id, "approver-1")

        assert approved.status == "APPROVED"
        assert approved.approver == "approver-1"
        assert approved.decided_at is not None

    def test_reject_with_reason(self):
        service = _build()
        request = service.create("session-1", "delete_dataset", "researcher-1")

        rejected = service.reject(request.request_id, "approver-1", "insufficient justification")

        assert rejected.status == "REJECTED"
        assert rejected.approver == "approver-1"
        assert rejected.reason == "insufficient justification"

    def test_reject_without_reason_is_an_error(self):
        service = _build()
        request = service.create("session-1", "delete_dataset", "researcher-1")

        with pytest.raises(Error):
            service.reject(request.request_id, "approver-1", "")

    def test_invalid_state_transition_is_an_error(self):
        service = _build()
        request = service.create("session-1", "delete_dataset", "researcher-1")
        service.reject(request.request_id, "approver-1", "not needed")

        with pytest.raises(Error):
            service.approve(request.request_id, "approver-2")

    def test_pending_lookup(self):
        service = _build()
        first = service.create("session-1", "delete_dataset", "researcher-1")
        second = service.create("session-1", "export_data", "researcher-2")
        service.approve(first.request_id, "approver-1")

        pending = service.pending("session-1")

        assert pending == [second]

    def test_duplicate_approval_is_rejected(self):
        service = _build()
        request = service.create("session-1", "delete_dataset", "researcher-1")
        service.approve(request.request_id, "approver-1")

        with pytest.raises(Error):
            service.approve(request.request_id, "approver-2")

    def test_status_lookup(self):
        service = _build()
        request = service.create("session-1", "delete_dataset", "researcher-1")

        assert service.status(request.request_id) == "PENDING"

        service.approve(request.request_id, "approver-1")

        assert service.status(request.request_id) == "APPROVED"

    def test_status_unknown_request_is_an_error(self):
        service = _build()

        with pytest.raises(Error):
            service.status("unknown-request")
