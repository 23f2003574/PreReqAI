import math

import pytest

from backend.session import (
    ExecutionNetworkTrafficShaper,
    ExecutionNetworkTrafficShaperError as Error,
    ExecutionNetworkTrafficShapingService,
)


class TestExecutionNetworkTrafficShapingService:
    def test_configure_shaper(self):
        service = ExecutionNetworkTrafficShapingService()

        shaper = service.configure("runtime-1", "INGRESS", 100, 200)

        assert isinstance(shaper, ExecutionNetworkTrafficShaper)
        assert shaper.runtime_id == "runtime-1"
        assert shaper.direction == "INGRESS"
        assert shaper.rate_limit == 100
        assert shaper.burst_limit == 200
        assert shaper.enabled is True
        assert service.remaining("runtime-1", "INGRESS") == pytest.approx(200, abs=1)

    def test_traffic_within_rate(self):
        service = ExecutionNetworkTrafficShapingService()
        service.configure("runtime-1", "INGRESS", 100, 100)

        assert service.allow("runtime-1", "INGRESS", 40) is True
        assert service.remaining("runtime-1", "INGRESS") == pytest.approx(60, abs=1)

    def test_burst_handling(self):
        service = ExecutionNetworkTrafficShapingService()
        service.configure("runtime-1", "INGRESS", 1, 10)

        assert service.allow("runtime-1", "INGRESS", 10) is True
        assert service.allow("runtime-1", "INGRESS", 1) is False

    def test_rate_exhaustion(self):
        service = ExecutionNetworkTrafficShapingService()
        service.configure("runtime-1", "EGRESS", 10, 10)
        service.allow("runtime-1", "EGRESS", 10)

        assert service.allow("runtime-1", "EGRESS", 1) is False
        assert service.remaining("runtime-1", "EGRESS") == pytest.approx(0, abs=1)

    def test_direction_isolation(self):
        service = ExecutionNetworkTrafficShapingService()
        service.configure("runtime-1", "INGRESS", 10, 10)
        service.configure("runtime-1", "EGRESS", 10, 10)

        service.allow("runtime-1", "INGRESS", 10)

        assert service.allow("runtime-1", "INGRESS", 1) is False
        assert service.allow("runtime-1", "EGRESS", 10) is True

    def test_reset(self):
        service = ExecutionNetworkTrafficShapingService()
        service.configure("runtime-1", "INGRESS", 10, 10)
        service.configure("runtime-1", "EGRESS", 10, 10)
        service.allow("runtime-1", "INGRESS", 10)
        service.allow("runtime-1", "EGRESS", 5)

        service.reset("runtime-1")

        assert service.remaining("runtime-1", "INGRESS") == pytest.approx(10, abs=1)
        assert service.remaining("runtime-1", "EGRESS") == pytest.approx(10, abs=1)

    def test_disabled_shaper_allows_traffic(self):
        service = ExecutionNetworkTrafficShapingService()
        service.configure("runtime-1", "INGRESS", 1, 1, enabled=False)

        assert service.allow("runtime-1", "INGRESS", 1000) is True
        assert service.remaining("runtime-1", "INGRESS") == math.inf

    def test_reconfigure_resets_bucket(self):
        service = ExecutionNetworkTrafficShapingService()
        service.configure("runtime-1", "INGRESS", 10, 10)
        service.allow("runtime-1", "INGRESS", 10)

        service.configure("runtime-1", "INGRESS", 10, 10)

        assert service.remaining("runtime-1", "INGRESS") == pytest.approx(10, abs=1)

    def test_operations_without_configured_shaper_are_rejected(self):
        service = ExecutionNetworkTrafficShapingService()

        with pytest.raises(Error):
            service.allow("runtime-1", "INGRESS", 1)

        with pytest.raises(Error):
            service.remaining("runtime-1", "INGRESS")

        with pytest.raises(Error):
            service.reset("runtime-1")

    def test_rate_and_burst_must_be_positive(self):
        service = ExecutionNetworkTrafficShapingService()

        with pytest.raises(Error):
            service.configure("runtime-1", "INGRESS", 0, 10)

        with pytest.raises(Error):
            service.configure("runtime-1", "INGRESS", 10, 0)

    def test_allow_rejects_invalid_direction_and_amount(self):
        service = ExecutionNetworkTrafficShapingService()
        service.configure("runtime-1", "INGRESS", 10, 10)

        with pytest.raises(Error):
            service.allow("runtime-1", "SIDEWAYS", 1)

        with pytest.raises(Error):
            service.allow("runtime-1", "INGRESS", 0)
