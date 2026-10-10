import pytest

from backend.session import (
    ExecutionApprovalQuorum,
    ExecutionApprovalQuorumError as Error,
    ExecutionApprovalQuorumService,
)


def _build():
    return ExecutionApprovalQuorumService()


class TestExecutionApprovalQuorumService:
    def test_create_quorum(self):
        service = _build()

        quorum = service.create("request-1", 2)

        assert isinstance(quorum, ExecutionApprovalQuorum)
        assert quorum.request_id == "request-1"
        assert quorum.required_count == 2
        assert quorum.approvers == ()
        assert quorum.status == "PENDING"

    def test_invalid_required_count_is_an_error(self):
        service = _build()

        with pytest.raises(Error):
            service.create("request-1", 0)

    def test_multiple_approvals(self):
        service = _build()
        quorum = service.create("request-1", 2)

        first = service.approve(quorum.quorum_id, "approver-1")
        second = service.approve(quorum.quorum_id, "approver-2")

        assert first.approvers == ("approver-1",)
        assert second.approvers == ("approver-1", "approver-2")

    def test_duplicate_approver_is_rejected(self):
        service = _build()
        quorum = service.create("request-1", 2)
        service.approve(quorum.quorum_id, "approver-1")

        with pytest.raises(Error):
            service.approve(quorum.quorum_id, "approver-1")

    def test_remaining_count(self):
        service = _build()
        quorum = service.create("request-1", 3)
        service.approve(quorum.quorum_id, "approver-1")

        assert service.remaining(quorum.quorum_id) == 2

    def test_quorum_satisfaction(self):
        service = _build()
        quorum = service.create("request-1", 2)

        assert service.satisfied(quorum.quorum_id) is False

        service.approve(quorum.quorum_id, "approver-1")
        service.approve(quorum.quorum_id, "approver-2")

        assert service.satisfied(quorum.quorum_id) is True
        assert service.remaining(quorum.quorum_id) == 0
