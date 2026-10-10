import pytest

from backend.session import (
    ExecutionJobDependency,
    ExecutionJobDependencyError as Error,
    ExecutionJobDependencyService,
)


class _FakeStatusService:
    def __init__(self, status_by_job=None):
        self._status_by_job = dict(status_by_job or {})

    def status(self, job_id):
        if job_id not in self._status_by_job:
            raise ValueError(f"unknown job {job_id!r}")

        return self._status_by_job[job_id]

    def set_status(self, job_id, status):
        self._status_by_job[job_id] = status


def _build(status_by_job=None):
    status_service = _FakeStatusService(
        status_by_job or {"job-1": "QUEUED", "job-2": "QUEUED", "job-3": "QUEUED"}
    )
    return status_service, ExecutionJobDependencyService(status_service)


class TestExecutionJobDependencyService:
    def test_add_returns_the_dependency_record(self):
        _, service = _build()

        record = service.add("job-1", "job-2")

        assert isinstance(record, ExecutionJobDependency)
        assert record.job_id == "job-1"
        assert record.depends_on == "job-2"
        assert record.required_status == "SUCCEEDED"

    def test_add_and_remove_dependency(self):
        _, service = _build()
        service.add("job-1", "job-2")

        service.remove("job-1", "job-2")

        assert service.dependencies("job-1") == ()

    def test_removing_unregistered_dependency_is_an_error(self):
        _, service = _build()

        with pytest.raises(Error):
            service.remove("job-1", "job-2")

    def test_multiple_dependencies(self):
        _, service = _build()
        service.add("job-1", "job-2")
        service.add("job-1", "job-3")

        recorded = service.dependencies("job-1")

        assert [record.depends_on for record in recorded] == ["job-2", "job-3"]

    def test_job_with_no_dependencies_is_ready(self):
        _, service = _build()

        assert service.ready("job-1") is True

    def test_dependency_readiness_when_dependency_succeeds(self):
        status_service, service = _build()
        service.add("job-1", "job-2")

        assert service.ready("job-1") is False

        status_service.set_status("job-2", "SUCCEEDED")

        assert service.ready("job-1") is True

    def test_failed_dependency_blocks_readiness(self):
        status_service, service = _build()
        service.add("job-1", "job-2")
        status_service.set_status("job-2", "FAILED")

        assert service.ready("job-1") is False

    def test_ready_requires_all_dependencies_to_succeed(self):
        status_service, service = _build()
        service.add("job-1", "job-2")
        service.add("job-1", "job-3")
        status_service.set_status("job-2", "SUCCEEDED")

        assert service.ready("job-1") is False

        status_service.set_status("job-3", "SUCCEEDED")

        assert service.ready("job-1") is True

    def test_self_dependency_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.add("job-1", "job-1")

    def test_dependency_on_unknown_job_is_rejected(self):
        _, service = _build()

        with pytest.raises(Error):
            service.add("job-1", "does-not-exist")

    def test_direct_cycle_is_rejected(self):
        _, service = _build()
        service.add("job-1", "job-2")

        with pytest.raises(Error):
            service.add("job-2", "job-1")

    def test_transitive_cycle_is_rejected(self):
        _, service = _build()
        service.add("job-1", "job-2")
        service.add("job-2", "job-3")

        with pytest.raises(Error):
            service.add("job-3", "job-1")
