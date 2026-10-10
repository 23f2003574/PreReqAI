import pytest

from backend.session import (
    ExecutionConcurrencyError as Error,
    ExecutionConcurrencyLimit,
    ExecutionConcurrencyService,
)


def _build():
    return ExecutionConcurrencyService()


class TestExecutionConcurrencyService:
    def test_register_limit(self):
        service = _build()

        limit = service.register("scope-1", 2)

        assert isinstance(limit, ExecutionConcurrencyLimit)
        assert limit.scope_id == "scope-1"
        assert limit.max_running == 2
        assert limit.enabled is True

    def test_invalid_max_running_is_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.register("scope-1", 0)

    def test_capacity_check(self):
        service = _build()
        service.register("scope-1", 1)

        assert service.can_start("scope-1") is True

        service.acquire("scope-1", "job-1")

        assert service.can_start("scope-1") is False

    def test_acquire_and_release(self):
        service = _build()
        service.register("scope-1", 1)

        service.acquire("scope-1", "job-1")
        assert service.running("scope-1") == 1

        service.release("scope-1", "job-1")
        assert service.running("scope-1") == 0
        assert service.can_start("scope-1") is True

    def test_release_restores_capacity_for_reacquire(self):
        service = _build()
        service.register("scope-1", 1)
        service.acquire("scope-1", "job-1")
        service.release("scope-1", "job-1")

        service.acquire("scope-1", "job-2")

        assert service.running("scope-1") == 1

    def test_capacity_exhaustion_is_rejected(self):
        service = _build()
        service.register("scope-1", 1)
        service.acquire("scope-1", "job-1")

        with pytest.raises(Error):
            service.acquire("scope-1", "job-2")

    def test_duplicate_acquire_is_rejected(self):
        service = _build()
        service.register("scope-1", 2)
        service.acquire("scope-1", "job-1")

        with pytest.raises(Error):
            service.acquire("scope-1", "job-1")

    def test_release_of_non_running_job_is_rejected(self):
        service = _build()
        service.register("scope-1", 1)

        with pytest.raises(Error):
            service.release("scope-1", "job-1")

    def test_operations_on_unregistered_scope_are_rejected(self):
        service = _build()

        with pytest.raises(Error):
            service.acquire("scope-1", "job-1")

        with pytest.raises(Error):
            service.can_start("scope-1")

        with pytest.raises(Error):
            service.running("scope-1")

    def test_scope_isolation(self):
        service = _build()
        service.register("scope-1", 1)
        service.register("scope-2", 1)

        service.acquire("scope-1", "job-1")

        assert service.can_start("scope-1") is False
        assert service.can_start("scope-2") is True

        service.acquire("scope-2", "job-1")

        assert service.running("scope-1") == 1
        assert service.running("scope-2") == 1

    def test_reregistering_a_scope_preserves_running_jobs(self):
        service = _build()
        service.register("scope-1", 2)
        service.acquire("scope-1", "job-1")

        service.register("scope-1", 3)

        assert service.running("scope-1") == 1
        assert service.can_start("scope-1") is True
