import pytest

from backend.session import (
    ExecutionStorageQuota,
    ExecutionStorageQuotaError as Error,
    ExecutionStorageQuotaService,
)


class TestExecutionStorageQuotaService:
    def test_configure_and_usage(self):
        service = ExecutionStorageQuotaService()

        quota = service.configure("scope-1", 100)

        assert isinstance(quota, ExecutionStorageQuota)
        assert quota.scope_id == "scope-1"
        assert quota.max_size == 100
        assert quota.used_size == 0
        assert quota.enabled is True

        assert service.usage("scope-1") == quota

        with pytest.raises(Error):
            service.configure("scope-1", 0)

        with pytest.raises(Error):
            service.configure("scope-1", -10)

    def test_allocation_within_quota(self):
        service = ExecutionStorageQuotaService()
        service.configure("scope-1", 100)

        assert service.can_allocate("scope-1", 40) is True

        updated = service.allocate("scope-1", 40)

        assert updated.used_size == 40
        assert service.usage("scope-1").used_size == 40

    def test_quota_exhaustion(self):
        service = ExecutionStorageQuotaService()
        service.configure("scope-1", 100)
        service.allocate("scope-1", 90)

        assert service.can_allocate("scope-1", 20) is False

        with pytest.raises(Error):
            service.allocate("scope-1", 20)

        assert service.usage("scope-1").used_size == 90

    def test_release(self):
        service = ExecutionStorageQuotaService()
        service.configure("scope-1", 100)
        service.allocate("scope-1", 60)

        updated = service.release("scope-1", 25)

        assert updated.used_size == 35
        assert service.usage("scope-1").used_size == 35

    def test_over_release_rejection(self):
        service = ExecutionStorageQuotaService()
        service.configure("scope-1", 100)
        service.allocate("scope-1", 10)

        with pytest.raises(Error):
            service.release("scope-1", 20)

        assert service.usage("scope-1").used_size == 10

    def test_scope_isolation(self):
        service = ExecutionStorageQuotaService()
        service.configure("scope-1", 100)
        service.configure("scope-2", 50)

        service.allocate("scope-1", 80)

        assert service.usage("scope-1").used_size == 80
        assert service.usage("scope-2").used_size == 0

        with pytest.raises(Error):
            service.allocate("scope-2", 60)

        assert service.can_allocate("scope-2", 30) is True
