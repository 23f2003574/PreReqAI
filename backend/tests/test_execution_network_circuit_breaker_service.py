import time

import pytest

from backend.session import (
    ExecutionNetworkCircuit,
    ExecutionNetworkCircuitError as Error,
    ExecutionNetworkCircuitBreakerService,
)


class TestExecutionNetworkCircuitBreakerService:
    def test_new_endpoint_starts_closed(self):
        service = ExecutionNetworkCircuitBreakerService(failure_threshold=3)

        assert service.state("endpoint-1") == "CLOSED"
        assert service.allow("endpoint-1") is True

    def test_failure_threshold(self):
        service = ExecutionNetworkCircuitBreakerService(failure_threshold=3)

        first = service.record_failure("endpoint-1")
        second = service.record_failure("endpoint-1")

        assert isinstance(first, ExecutionNetworkCircuit)
        assert first.failure_count == 1
        assert first.state == "CLOSED"
        assert second.failure_count == 2
        assert second.state == "CLOSED"

    def test_circuit_opening(self):
        service = ExecutionNetworkCircuitBreakerService(failure_threshold=3)
        service.record_failure("endpoint-1")
        service.record_failure("endpoint-1")

        opened = service.record_failure("endpoint-1")

        assert opened.state == "OPEN"
        assert opened.failure_count == 3
        assert opened.opened_at is not None
        assert service.state("endpoint-1") == "OPEN"

    def test_traffic_rejection(self):
        service = ExecutionNetworkCircuitBreakerService(
            failure_threshold=1, recovery_timeout_seconds=60
        )
        service.record_failure("endpoint-1")

        assert service.allow("endpoint-1") is False

    def test_half_open_recovery(self):
        service = ExecutionNetworkCircuitBreakerService(
            failure_threshold=1, recovery_timeout_seconds=0.05
        )
        service.record_failure("endpoint-1")
        assert service.allow("endpoint-1") is False

        time.sleep(0.1)

        assert service.allow("endpoint-1") is True
        assert service.state("endpoint-1") == "HALF_OPEN"

        closed = service.record_success("endpoint-1")

        assert closed.state == "CLOSED"
        assert closed.failure_count == 0
        assert closed.opened_at is None

    def test_half_open_failure(self):
        service = ExecutionNetworkCircuitBreakerService(
            failure_threshold=1, recovery_timeout_seconds=0.05
        )
        service.record_failure("endpoint-1")
        time.sleep(0.1)
        service.allow("endpoint-1")
        assert service.state("endpoint-1") == "HALF_OPEN"

        reopened = service.record_failure("endpoint-1")

        assert reopened.state == "OPEN"
        assert reopened.opened_at is not None
        assert service.allow("endpoint-1") is False

    def test_success_reset(self):
        service = ExecutionNetworkCircuitBreakerService(failure_threshold=3)
        service.record_failure("endpoint-1")
        service.record_failure("endpoint-1")

        reset = service.record_success("endpoint-1")

        assert reset.state == "CLOSED"
        assert reset.failure_count == 0

        next_failure = service.record_failure("endpoint-1")
        assert next_failure.failure_count == 1

    def test_manual_open_and_close(self):
        service = ExecutionNetworkCircuitBreakerService(failure_threshold=3)

        opened = service.open("endpoint-1")
        assert opened.state == "OPEN"
        assert service.allow("endpoint-1") is False

        closed = service.close("endpoint-1")
        assert closed.state == "CLOSED"
        assert closed.failure_count == 0
        assert service.allow("endpoint-1") is True

    def test_endpoint_isolation(self):
        service = ExecutionNetworkCircuitBreakerService(failure_threshold=1)
        service.record_failure("endpoint-1")

        assert service.state("endpoint-1") == "OPEN"
        assert service.state("endpoint-2") == "CLOSED"
        assert service.allow("endpoint-2") is True

    def test_validation_rejects_blank_endpoint_id(self):
        service = ExecutionNetworkCircuitBreakerService()

        with pytest.raises(Error):
            service.record_failure("")

        with pytest.raises(Error):
            service.allow(None)
