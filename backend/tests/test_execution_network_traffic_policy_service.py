import pytest

from backend.session import (
    ExecutionNetworkTrafficPolicy,
    ExecutionNetworkTrafficPolicyError as Error,
    ExecutionNetworkTrafficPolicyService,
)


def _policy(policy_id, runtime_id, direction, protocols, allowed, endpoint_id=None):
    return ExecutionNetworkTrafficPolicy(
        policy_id=policy_id,
        runtime_id=runtime_id,
        direction=direction,
        protocols=protocols,
        allowed=allowed,
        endpoint_id=endpoint_id,
    )


class TestExecutionNetworkTrafficPolicyService:
    def test_allowed_traffic(self):
        service = ExecutionNetworkTrafficPolicyService()
        service.register(_policy("policy-1", "runtime-1", "INGRESS", ("HTTP",), True))

        assert service.evaluate("runtime-1", "endpoint-1", "INGRESS", "HTTP") is True

    def test_denied_traffic_by_explicit_deny_policy(self):
        service = ExecutionNetworkTrafficPolicyService()
        service.register(_policy("policy-1", "runtime-1", "INGRESS", ("HTTP",), False))

        assert service.evaluate("runtime-1", "endpoint-1", "INGRESS", "HTTP") is False

    def test_default_deny_with_no_matching_policy(self):
        service = ExecutionNetworkTrafficPolicyService()

        assert service.evaluate("runtime-1", "endpoint-1", "INGRESS", "HTTP") is False

    def test_ingress_egress_isolation(self):
        service = ExecutionNetworkTrafficPolicyService()
        service.register(_policy("policy-1", "runtime-1", "INGRESS", ("HTTP",), True))

        assert service.evaluate("runtime-1", "endpoint-1", "INGRESS", "HTTP") is True
        assert service.evaluate("runtime-1", "endpoint-1", "EGRESS", "HTTP") is False

    def test_protocol_filtering(self):
        service = ExecutionNetworkTrafficPolicyService()
        service.register(_policy("policy-1", "runtime-1", "EGRESS", ("HTTPS",), True))

        assert service.evaluate("runtime-1", "endpoint-1", "EGRESS", "HTTPS") is True
        assert service.evaluate("runtime-1", "endpoint-1", "EGRESS", "TCP") is False

    def test_endpoint_override(self):
        service = ExecutionNetworkTrafficPolicyService()
        service.register(_policy("policy-runtime", "runtime-1", "INGRESS", ("HTTP",), True))
        service.register(
            _policy("policy-endpoint", "runtime-1", "INGRESS", ("HTTP",), False, endpoint_id="endpoint-1")
        )

        assert service.evaluate("runtime-1", "endpoint-1", "INGRESS", "HTTP") is False
        assert service.evaluate("runtime-1", "endpoint-2", "INGRESS", "HTTP") is True

    def test_disabled_policy_ignored(self):
        service = ExecutionNetworkTrafficPolicyService()
        policy = _policy("policy-1", "runtime-1", "INGRESS", ("HTTP",), True)
        service.register(policy)

        assert service.evaluate("runtime-1", "endpoint-1", "INGRESS", "HTTP") is True

        disabled = service.disable(policy.policy_id)

        assert disabled.policy_id == policy.policy_id
        assert service.evaluate("runtime-1", "endpoint-1", "INGRESS", "HTTP") is False

    def test_disabled_endpoint_override_falls_back_to_runtime_default(self):
        service = ExecutionNetworkTrafficPolicyService()
        service.register(_policy("policy-runtime", "runtime-1", "INGRESS", ("HTTP",), True))
        override = _policy(
            "policy-endpoint", "runtime-1", "INGRESS", ("HTTP",), False, endpoint_id="endpoint-1"
        )
        service.register(override)
        service.disable(override.policy_id)

        assert service.evaluate("runtime-1", "endpoint-1", "INGRESS", "HTTP") is True

    def test_disable_is_idempotent(self):
        service = ExecutionNetworkTrafficPolicyService()
        policy = _policy("policy-1", "runtime-1", "INGRESS", ("HTTP",), True)
        service.register(policy)

        service.disable(policy.policy_id)
        service.disable(policy.policy_id)

        assert service.evaluate("runtime-1", "endpoint-1", "INGRESS", "HTTP") is False

    def test_most_recent_policy_wins_at_same_specificity(self):
        service = ExecutionNetworkTrafficPolicyService()
        service.register(_policy("policy-1", "runtime-1", "INGRESS", ("HTTP",), True))
        service.register(_policy("policy-2", "runtime-1", "INGRESS", ("HTTP",), False))

        assert service.evaluate("runtime-1", "endpoint-1", "INGRESS", "HTTP") is False

    def test_policies_lookup(self):
        service = ExecutionNetworkTrafficPolicyService()
        first = _policy("policy-1", "runtime-1", "INGRESS", ("HTTP",), True)
        second = _policy("policy-2", "runtime-1", "EGRESS", ("TCP",), False)
        service.register(first)
        service.register(second)
        service.register(_policy("policy-3", "runtime-2", "INGRESS", ("HTTP",), True))

        policies = service.policies("runtime-1")

        assert [policy.policy_id for policy in policies] == ["policy-1", "policy-2"]

    def test_duplicate_registration_is_rejected(self):
        service = ExecutionNetworkTrafficPolicyService()
        policy = _policy("policy-1", "runtime-1", "INGRESS", ("HTTP",), True)
        service.register(policy)

        with pytest.raises(Error):
            service.register(policy)

    def test_disable_unknown_policy_is_rejected(self):
        service = ExecutionNetworkTrafficPolicyService()

        with pytest.raises(Error):
            service.disable("does-not-exist")

    def test_evaluate_rejects_unknown_direction_and_protocol(self):
        service = ExecutionNetworkTrafficPolicyService()

        with pytest.raises(Error):
            service.evaluate("runtime-1", "endpoint-1", "SIDEWAYS", "HTTP")

        with pytest.raises(Error):
            service.evaluate("runtime-1", "endpoint-1", "INGRESS", "FTP")
