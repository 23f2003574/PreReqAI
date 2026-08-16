import pytest

from backend.session import (
    ExecutionJob,
    ExecutionJobPriority,
    ExecutionJobPriorityError as Error,
    ExecutionJobPriorityService,
    ExecutionJobQueueService,
)


def _build():
    queue = ExecutionJobQueueService()
    return queue, ExecutionJobPriorityService(queue)


def _job(job_id, session_id="session-1", payload=None):
    return ExecutionJob(job_id=job_id, session_id=session_id, payload=payload)


class TestExecutionJobPriorityService:
    def test_set_returns_the_priority_record(self):
        queue, service = _build()
        queue.enqueue(_job("job-1"))

        record = service.set("job-1", "HIGH")

        assert isinstance(record, ExecutionJobPriority)
        assert record.job_id == "job-1"
        assert record.priority == "HIGH"

    def test_get_returns_the_current_priority(self):
        queue, service = _build()
        queue.enqueue(_job("job-1"))
        service.set("job-1", "CRITICAL")

        assert service.get("job-1").priority == "CRITICAL"

    def test_priority_ordering(self):
        queue, service = _build()
        queue.enqueue(_job("job-1"))
        queue.enqueue(_job("job-2"))
        queue.enqueue(_job("job-3"))

        service.set("job-1", "LOW")
        service.set("job-2", "CRITICAL")
        service.set("job-3", "NORMAL")

        assert [record.job_id for record in service.ordered()] == ["job-2", "job-3", "job-1"]
        assert service.highest().job_id == "job-2"

    def test_same_priority_fifo(self):
        queue, service = _build()
        queue.enqueue(_job("job-1"))
        queue.enqueue(_job("job-2"))
        queue.enqueue(_job("job-3"))

        service.set("job-1", "HIGH")
        service.set("job-2", "HIGH")
        service.set("job-3", "HIGH")

        assert [record.job_id for record in service.ordered()] == ["job-1", "job-2", "job-3"]

    def test_priority_update_changes_rank_and_fifo_position(self):
        queue, service = _build()
        queue.enqueue(_job("job-1"))
        queue.enqueue(_job("job-2"))

        service.set("job-1", "HIGH")
        service.set("job-2", "HIGH")

        service.set("job-1", "HIGH")

        assert service.get("job-1").priority == "HIGH"
        assert [record.job_id for record in service.ordered()] == ["job-2", "job-1"]

    def test_cancelled_job_excluded_from_ordering(self):
        queue, service = _build()
        queue.enqueue(_job("job-1"))
        queue.enqueue(_job("job-2"))

        service.set("job-1", "CRITICAL")
        service.set("job-2", "LOW")
        queue.cancel("job-1")

        assert [record.job_id for record in service.ordered()] == ["job-2"]
        assert service.highest().job_id == "job-2"

    def test_highest_is_none_when_nothing_queued(self):
        queue, service = _build()
        queue.enqueue(_job("job-1"))
        service.set("job-1", "HIGH")
        queue.cancel("job-1")

        assert service.highest() is None

    def test_set_on_unknown_job_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.set("does-not-exist", "HIGH")

    def test_get_on_unset_job_is_rejected(self):
        queue, service = _build()
        queue.enqueue(_job("job-1"))

        with pytest.raises(Error):
            service.get("job-1")

    def test_set_with_invalid_priority_is_rejected(self):
        queue, service = _build()
        queue.enqueue(_job("job-1"))

        with pytest.raises(Error):
            service.set("job-1", "URGENT")
