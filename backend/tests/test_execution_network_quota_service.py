import math
import time

import pytest

from backend.session import (
    ExecutionNetworkQuota,
    ExecutionNetworkQuotaError as Error,
    ExecutionNetworkQuotaService,
)


def _limits(ingress_limit=100, egress_limit=50, window_seconds=60, enabled=True):
    return {
        "ingress_limit": ingress_limit,
        "egress_limit": egress_limit,
        "window_seconds": window_seconds,
        "enabled": enabled,
    }


class TestExecutionNetworkQuotaService:
    def test_configure_quota(self):
        service = ExecutionNetworkQuotaService()

        quota = service.configure("runtime-1", _limits(ingress_limit=100, egress_limit=50))

        assert isinstance(quota, ExecutionNetworkQuota)
        assert quota.runtime_id == "runtime-1"
        assert quota.ingress_limit == 100
        assert quota.egress_limit == 50
        assert quota.enabled is True

    def test_limits_must_be_positive(self):
        service = ExecutionNetworkQuotaService()

        with pytest.raises(Error):
            service.configure("runtime-1", _limits(ingress_limit=0))

        with pytest.raises(Error):
            service.configure("runtime-1", _limits(egress_limit=-1))

        with pytest.raises(Error):
            service.configure("runtime-1", _limits(window_seconds=0))

    def test_consume_within_limit(self):
        service = ExecutionNetworkQuotaService()
        service.configure("runtime-1", _limits(ingress_limit=100))

        remaining = service.consume("runtime-1", "INGRESS", 40)

        assert remaining == 60
        assert service.available("runtime-1", "INGRESS") == 60

    def test_quota_exhaustion(self):
        service = ExecutionNetworkQuotaService()
        service.configure("runtime-1", _limits(ingress_limit=100))
        service.consume("runtime-1", "INGRESS", 90)

        with pytest.raises(Error):
            service.consume("runtime-1", "INGRESS", 20)

        assert service.available("runtime-1", "INGRESS") == 10

    def test_ingress_egress_isolation(self):
        service = ExecutionNetworkQuotaService()
        service.configure("runtime-1", _limits(ingress_limit=100, egress_limit=50))
        service.consume("runtime-1", "INGRESS", 80)

        assert service.available("runtime-1", "INGRESS") == 20
        assert service.available("runtime-1", "EGRESS") == 50

        service.consume("runtime-1", "EGRESS", 50)

        with pytest.raises(Error):
            service.consume("runtime-1", "EGRESS", 1)

        assert service.available("runtime-1", "INGRESS") == 20

    def test_reset(self):
        service = ExecutionNetworkQuotaService()
        service.configure("runtime-1", _limits(ingress_limit=100, egress_limit=50))
        service.consume("runtime-1", "INGRESS", 90)
        service.consume("runtime-1", "EGRESS", 40)

        service.reset("runtime-1")

        assert service.available("runtime-1", "INGRESS") == 100
        assert service.available("runtime-1", "EGRESS") == 50

    def test_disabled_quota(self):
        service = ExecutionNetworkQuotaService()
        service.configure("runtime-1", _limits(ingress_limit=10, enabled=False))

        remaining = service.consume("runtime-1", "INGRESS", 1000)

        assert remaining == math.inf
        assert service.available("runtime-1", "INGRESS") == math.inf

    def test_reconfigure_clears_prior_usage(self):
        service = ExecutionNetworkQuotaService()
        service.configure("runtime-1", _limits(ingress_limit=100))
        service.consume("runtime-1", "INGRESS", 90)

        service.configure("runtime-1", _limits(ingress_limit=100))

        assert service.available("runtime-1", "INGRESS") == 100

    def test_window_rollover(self):
        service = ExecutionNetworkQuotaService()
        service.configure("runtime-1", _limits(ingress_limit=10, window_seconds=0.05))
        service.consume("runtime-1", "INGRESS", 10)

        with pytest.raises(Error):
            service.consume("runtime-1", "INGRESS", 1)

        time.sleep(0.1)

        assert service.available("runtime-1", "INGRESS") == 10
        remaining = service.consume("runtime-1", "INGRESS", 5)
        assert remaining == 5

    def test_consume_without_configured_quota_is_rejected(self):
        service = ExecutionNetworkQuotaService()

        with pytest.raises(Error):
            service.consume("runtime-1", "INGRESS", 1)

    def test_available_without_configured_quota_is_rejected(self):
        service = ExecutionNetworkQuotaService()

        with pytest.raises(Error):
            service.available("runtime-1", "INGRESS")

    def test_reset_without_configured_quota_is_rejected(self):
        service = ExecutionNetworkQuotaService()

        with pytest.raises(Error):
            service.reset("runtime-1")

    def test_consume_rejects_invalid_direction_and_amount(self):
        service = ExecutionNetworkQuotaService()
        service.configure("runtime-1", _limits())

        with pytest.raises(Error):
            service.consume("runtime-1", "SIDEWAYS", 1)

        with pytest.raises(Error):
            service.consume("runtime-1", "INGRESS", 0)

        with pytest.raises(Error):
            service.consume("runtime-1", "INGRESS", -5)
