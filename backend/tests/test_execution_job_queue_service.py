import pytest

from backend.session import (
    ExecutionJob,
    ExecutionJobError as Error,
    ExecutionJobQueueService,
)


def _build():
    return ExecutionJobQueueService()


def _job(job_id="job-1", session_id="session-1", payload=None):
    return ExecutionJob(job_id=job_id, session_id=session_id, payload=payload)


class TestExecutionJobQueueService:
    def test_enqueue_returns_the_queued_job(self):
        service = _build()

        job = service.enqueue(_job())

        assert isinstance(job, ExecutionJob)
        assert job.job_id == "job-1"
        assert job.status == "QUEUED"
        assert service.size() == 1

    def test_dequeue_transitions_to_ready(self):
        service = _build()
        service.enqueue(_job())

        dequeued = service.dequeue()

        assert dequeued.job_id == "job-1"
        assert dequeued.status == "READY"
        assert service.status("job-1") == "READY"
        assert service.size() == 0

    def test_fifo_ordering(self):
        service = _build()
        service.enqueue(_job("job-1"))
        service.enqueue(_job("job-2"))
        service.enqueue(_job("job-3"))

        assert service.dequeue().job_id == "job-1"
        assert service.dequeue().job_id == "job-2"
        assert service.dequeue().job_id == "job-3"

    def test_peek_does_not_mutate_the_queue(self):
        service = _build()
        service.enqueue(_job("job-1"))
        service.enqueue(_job("job-2"))

        peeked = service.peek()

        assert peeked.job_id == "job-1"
        assert peeked.status == "QUEUED"
        assert service.size() == 2
        assert service.dequeue().job_id == "job-1"

    def test_peek_on_empty_queue_returns_none(self):
        service = _build()

        assert service.peek() is None

    def test_cancel_marks_job_cancelled_and_removes_from_queue(self):
        service = _build()
        service.enqueue(_job("job-1"))
        service.enqueue(_job("job-2"))

        cancelled = service.cancel("job-1")

        assert cancelled.status == "CANCELLED"
        assert service.status("job-1") == "CANCELLED"
        assert service.size() == 1
        assert service.dequeue().job_id == "job-2"

    def test_cancelled_job_can_never_be_dequeued(self):
        service = _build()
        service.enqueue(_job("job-1"))
        service.cancel("job-1")

        assert service.dequeue() is None

    def test_cancelling_a_ready_job_is_an_error(self):
        service = _build()
        service.enqueue(_job("job-1"))
        service.dequeue()

        with pytest.raises(Error):
            service.cancel("job-1")

    def test_cancelling_an_already_cancelled_job_is_an_error(self):
        service = _build()
        service.enqueue(_job("job-1"))
        service.cancel("job-1")

        with pytest.raises(Error):
            service.cancel("job-1")

    def test_cancelling_an_unknown_job_is_an_error(self):
        service = _build()

        with pytest.raises(Error):
            service.cancel("does-not-exist")

    def test_duplicate_job_enqueue_is_rejected(self):
        service = _build()
        service.enqueue(_job("job-1"))

        with pytest.raises(Error):
            service.enqueue(_job("job-1"))

    def test_enqueue_of_non_queued_job_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.enqueue(ExecutionJob(job_id="job-1", session_id="session-1", payload=None, status="READY"))

    def test_dequeue_on_empty_queue_returns_none(self):
        service = _build()

        assert service.dequeue() is None

    def test_status_of_unknown_job_is_an_error(self):
        service = _build()

        with pytest.raises(Error):
            service.status("does-not-exist")

    def test_size_reflects_only_queued_jobs(self):
        service = _build()
        service.enqueue(_job("job-1"))
        service.enqueue(_job("job-2"))
        service.dequeue()

        assert service.size() == 1
