import pytest

from backend.session import (
    ExecutionChangeRequest,
    ExecutionChangeRequestError as Error,
    ExecutionChangeRequestService,
)


def _build():
    return ExecutionChangeRequestService()


class TestExecutionChangeRequestService:
    def test_create_and_approve(self):
        service = _build()

        request = service.create("session-1", {"max_concurrency": "4"}, "researcher-1")

        assert isinstance(request, ExecutionChangeRequest)
        assert request.status == "PENDING"

        approved = service.approve(request.change_id, "approver-1")

        assert approved.status == "APPROVED"
        assert approved.approver == "approver-1"

    def test_rejection(self):
        service = _build()
        request = service.create("session-1", {"max_concurrency": "4"}, "researcher-1")

        rejected = service.reject(request.change_id, "approver-1", "not justified")

        assert rejected.status == "REJECTED"
        assert rejected.reason == "not justified"

    def test_apply_approved_change(self):
        service = _build()
        request = service.create("session-1", {"max_concurrency": "4"}, "researcher-1")
        service.approve(request.change_id, "approver-1")

        applied = service.apply(request.change_id)

        assert applied.status == "APPLIED"
        assert applied.applied_at is not None
        assert service.configuration("session-1") == {"max_concurrency": "4"}

    def test_rejected_apply_is_an_error(self):
        service = _build()
        request = service.create("session-1", {"max_concurrency": "4"}, "researcher-1")
        service.reject(request.change_id, "approver-1", "not justified")

        with pytest.raises(Error):
            service.apply(request.change_id)

    def test_apply_without_approval_is_an_error(self):
        service = _build()
        request = service.create("session-1", {"max_concurrency": "4"}, "researcher-1")

        with pytest.raises(Error):
            service.apply(request.change_id)

    def test_atomic_failure_leaves_configuration_untouched(self):
        service = _build()
        request = service.create(
            "session-1",
            {"max_concurrency": "4", "missing_key": None},
            "researcher-1",
        )
        service.approve(request.change_id, "approver-1")

        with pytest.raises(Error):
            service.apply(request.change_id)

        assert service.configuration("session-1") == {}
        assert service.status(request.change_id) == "APPROVED"

    def test_invalid_state_transition_is_an_error(self):
        service = _build()
        request = service.create("session-1", {"max_concurrency": "4"}, "researcher-1")
        service.approve(request.change_id, "approver-1")
        service.apply(request.change_id)

        with pytest.raises(Error):
            service.apply(request.change_id)

        with pytest.raises(Error):
            service.approve(request.change_id, "approver-2")
