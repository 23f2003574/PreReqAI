import math

import pytest

from backend.session import (
    ExecutionNetworkFailoverPolicy,
    ExecutionNetworkFailoverPolicyError as Error,
    ExecutionNetworkFailoverPolicyService,
)


class _FakeEndpoint:
    def __init__(self, endpoint_id):
        self.endpoint_id = endpoint_id


class _FakeEndpointService:
    def __init__(self):
        self._active = {}

    def set_active(self, runtime_id, endpoint_ids):
        self._active[runtime_id] = tuple(_FakeEndpoint(eid) for eid in endpoint_ids)

    def active(self, runtime_id):
        return self._active.get(runtime_id, ())


class _FakeHealth:
    def __init__(self, latency_ms):
        self.latency_ms = latency_ms


class _FakeHealthService:
    def __init__(self):
        self._healthy = {}
        self._latency = {}

    def set_healthy(self, endpoint_id, value):
        self._healthy[endpoint_id] = value

    def set_latency(self, endpoint_id, latency_ms):
        self._latency[endpoint_id] = latency_ms

    def healthy(self, endpoint_id):
        return self._healthy.get(endpoint_id, True)

    def check(self, endpoint_id):
        return _FakeHealth(self._latency.get(endpoint_id, 0))


class _FakeCircuitService:
    def __init__(self):
        self._state = {}

    def set_state(self, endpoint_id, state):
        self._state[endpoint_id] = state

    def state(self, endpoint_id):
        return self._state.get(endpoint_id, "CLOSED")


class _FakeQuotaService:
    def __init__(self):
        self._available = {}

    def set_available(self, runtime_id, direction, value):
        self._available[(runtime_id, direction)] = value

    def available(self, runtime_id, direction):
        return self._available.get((runtime_id, direction), math.inf)


def _build():
    endpoint_service = _FakeEndpointService()
    health_service = _FakeHealthService()
    circuit_service = _FakeCircuitService()
    quota_service = _FakeQuotaService()
    service = ExecutionNetworkFailoverPolicyService(
        endpoint_service, health_service, circuit_service, quota_service
    )

    return endpoint_service, health_service, circuit_service, quota_service, service


def _policy(policy_id, runtime_id, trigger, threshold, enabled=True):
    return ExecutionNetworkFailoverPolicy(
        policy_id=policy_id,
        runtime_id=runtime_id,
        trigger=trigger,
        threshold=threshold,
        enabled=enabled,
    )


class TestExecutionNetworkFailoverPolicyService:
    def test_register_and_evaluate_with_no_trigger(self):
        endpoint_service, _, _, _, service = _build()
        endpoint_service.set_active("runtime-1", ("endpoint-1",))
        policy = service.register(_policy("policy-1", "runtime-1", "UNHEALTHY", 1))

        assert isinstance(policy, ExecutionNetworkFailoverPolicy)
        assert service.evaluate("runtime-1") == ()

    def test_health_trigger(self):
        endpoint_service, health_service, _, _, service = _build()
        endpoint_service.set_active("runtime-1", ("endpoint-1",))
        health_service.set_healthy("endpoint-1", False)
        policy = service.register(_policy("policy-1", "runtime-1", "UNHEALTHY", 1))

        assert service.evaluate("runtime-1") == (policy,)

    def test_circuit_trigger(self):
        endpoint_service, _, circuit_service, _, service = _build()
        endpoint_service.set_active("runtime-1", ("endpoint-1",))
        circuit_service.set_state("endpoint-1", "OPEN")
        policy = service.register(_policy("policy-1", "runtime-1", "CIRCUIT_OPEN", 1))

        assert service.evaluate("runtime-1") == (policy,)

    def test_quota_trigger(self):
        endpoint_service, _, _, quota_service, service = _build()
        endpoint_service.set_active("runtime-1", ("endpoint-1",))
        quota_service.set_available("runtime-1", "INGRESS", 0)
        policy = service.register(_policy("policy-1", "runtime-1", "QUOTA_EXCEEDED", 1))

        assert service.evaluate("runtime-1") == (policy,)

    def test_quota_trigger_not_fired_with_capacity(self):
        endpoint_service, _, _, quota_service, service = _build()
        endpoint_service.set_active("runtime-1", ("endpoint-1",))
        quota_service.set_available("runtime-1", "INGRESS", 50)
        quota_service.set_available("runtime-1", "EGRESS", 50)
        service.register(_policy("policy-1", "runtime-1", "QUOTA_EXCEEDED", 1))

        assert service.evaluate("runtime-1") == ()

    def test_latency_trigger(self):
        endpoint_service, health_service, _, _, service = _build()
        endpoint_service.set_active("runtime-1", ("endpoint-1",))
        health_service.set_latency("endpoint-1", 500)
        policy = service.register(_policy("policy-1", "runtime-1", "LATENCY", 200))

        assert service.evaluate("runtime-1") == (policy,)

    def test_latency_trigger_not_fired_below_threshold(self):
        endpoint_service, health_service, _, _, service = _build()
        endpoint_service.set_active("runtime-1", ("endpoint-1",))
        health_service.set_latency("endpoint-1", 50)
        service.register(_policy("policy-1", "runtime-1", "LATENCY", 200))

        assert service.evaluate("runtime-1") == ()

    def test_disabled_policy_is_skipped(self):
        endpoint_service, health_service, _, _, service = _build()
        endpoint_service.set_active("runtime-1", ("endpoint-1",))
        health_service.set_healthy("endpoint-1", False)
        policy = service.register(_policy("policy-1", "runtime-1", "UNHEALTHY", 1))

        disabled = service.disable(policy.policy_id)

        assert disabled.enabled is False
        assert service.evaluate("runtime-1") == ()

    def test_multiple_triggers_coexist(self):
        endpoint_service, health_service, circuit_service, _, service = _build()
        endpoint_service.set_active("runtime-1", ("endpoint-1",))
        health_service.set_healthy("endpoint-1", False)
        circuit_service.set_state("endpoint-1", "OPEN")
        unhealthy_policy = service.register(_policy("policy-1", "runtime-1", "UNHEALTHY", 1))
        circuit_policy = service.register(_policy("policy-2", "runtime-1", "CIRCUIT_OPEN", 1))

        triggered = service.evaluate("runtime-1")

        assert triggered == (unhealthy_policy, circuit_policy)

    def test_evaluation_is_deterministic(self):
        endpoint_service, health_service, _, _, service = _build()
        endpoint_service.set_active("runtime-1", ("endpoint-1",))
        health_service.set_healthy("endpoint-1", False)
        policy = service.register(_policy("policy-1", "runtime-1", "UNHEALTHY", 1))

        results = [service.evaluate("runtime-1") for _ in range(5)]

        assert all(result == (policy,) for result in results)

    def test_policies_lookup(self):
        _, _, _, _, service = _build()
        first = service.register(_policy("policy-1", "runtime-1", "UNHEALTHY", 1))
        second = service.register(_policy("policy-2", "runtime-1", "LATENCY", 200))
        service.register(_policy("policy-3", "runtime-2", "CIRCUIT_OPEN", 1))

        assert service.policies("runtime-1") == (first, second)

    def test_duplicate_registration_is_rejected(self):
        _, _, _, _, service = _build()
        policy = service.register(_policy("policy-1", "runtime-1", "UNHEALTHY", 1))

        with pytest.raises(Error):
            service.register(policy)

    def test_disable_unknown_policy_is_rejected(self):
        _, _, _, _, service = _build()

        with pytest.raises(Error):
            service.disable("does-not-exist")

    def test_disable_is_idempotent(self):
        _, _, _, _, service = _build()
        policy = service.register(_policy("policy-1", "runtime-1", "UNHEALTHY", 1))

        first = service.disable(policy.policy_id)
        second = service.disable(policy.policy_id)

        assert first.enabled is False
        assert second.enabled is False
