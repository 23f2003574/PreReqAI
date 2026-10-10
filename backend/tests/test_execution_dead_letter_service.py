import pytest

from backend.session import (
    ExecutionDeadLetterError as Error,
    ExecutionDeadLetterJob,
    ExecutionDeadLetterService,
)


def _build(retry_threshold=2, on_retry=None):
    return ExecutionDeadLetterService(retry_threshold=retry_threshold, on_retry=on_retry)


def _move_until_dead_lettered(service, job_id, reason, attempts):
    record = None

    for _ in range(attempts):
        record = service.move(job_id, reason)

    return record


class TestExecutionDeadLetterService:
    def test_retry_threshold(self):
        service = _build(retry_threshold=2)

        assert service.move("job-1", "timeout") is None
        assert service.move("job-1", "timeout") is None
        assert service.move("job-1", "timeout") is not None

    def test_move_failed_job(self):
        service = _build(retry_threshold=1)

        record = _move_until_dead_lettered(service, "job-1", "out of memory", attempts=2)

        assert isinstance(record, ExecutionDeadLetterJob)
        assert record.job_id == "job-1"
        assert record.reason == "out of memory"
        assert record.failure_count == 2

    def test_metadata_preservation_through_retry(self):
        service = _build(retry_threshold=1)
        record = _move_until_dead_lettered(service, "job-1", "out of memory", attempts=2)

        retried = service.retry(record.dead_letter_id)

        assert retried is record
        assert retried.job_id == "job-1"
        assert retried.reason == "out of memory"
        assert retried.failure_count == 2

    def test_metadata_preservation_through_discard(self):
        service = _build(retry_threshold=1)
        record = _move_until_dead_lettered(service, "job-1", "out of memory", attempts=2)

        discarded = service.discard(record.dead_letter_id)

        assert discarded is record
        assert discarded.reason == "out of memory"

    def test_retry_invokes_on_retry_callback(self):
        requeued = []
        service = _build(retry_threshold=1, on_retry=requeued.append)
        record = _move_until_dead_lettered(service, "job-1", "timeout", attempts=2)

        service.retry(record.dead_letter_id)

        assert requeued == ["job-1"]

    def test_retry_resets_failure_count(self):
        service = _build(retry_threshold=1)
        record = _move_until_dead_lettered(service, "job-1", "timeout", attempts=2)
        service.retry(record.dead_letter_id)

        assert service.move("job-1", "timeout") is None

    def test_discard(self):
        service = _build(retry_threshold=1)
        record = _move_until_dead_lettered(service, "job-1", "timeout", attempts=2)

        discarded = service.discard(record.dead_letter_id)

        assert discarded.dead_letter_id == record.dead_letter_id

    def test_terminal_discard_rejects_further_retry(self):
        service = _build(retry_threshold=1)
        record = _move_until_dead_lettered(service, "job-1", "timeout", attempts=2)
        service.discard(record.dead_letter_id)

        with pytest.raises(Error):
            service.retry(record.dead_letter_id)

        with pytest.raises(Error):
            service.discard(record.dead_letter_id)

    def test_terminal_retry_rejects_further_discard(self):
        service = _build(retry_threshold=1)
        record = _move_until_dead_lettered(service, "job-1", "timeout", attempts=2)
        service.retry(record.dead_letter_id)

        with pytest.raises(Error):
            service.discard(record.dead_letter_id)

    def test_list_returns_every_record_for_a_job(self):
        service = _build(retry_threshold=1)
        first = _move_until_dead_lettered(service, "job-1", "timeout", attempts=2)
        service.retry(first.dead_letter_id)
        second = _move_until_dead_lettered(service, "job-1", "timeout", attempts=2)

        records = service.list("job-1")

        assert {record.dead_letter_id for record in records} == {first.dead_letter_id, second.dead_letter_id}

    def test_retrying_unknown_dead_letter_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.retry("does-not-exist")

    def test_invalid_retry_threshold_is_rejected(self):
        with pytest.raises(Error):
            ExecutionDeadLetterService(retry_threshold=0)
