import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicy as Policy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyService as PolicyService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePolicyAssignment as Assignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaService as QuotaService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget as Budget,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy as TimeoutPolicy,
)


def _policy(policy_id, name=None, enabled=True, retry_policy=None, timeout_policy=None, quota_policy=None):
    return Policy(
        policy_id=policy_id,
        name=name if name is not None else f"name-for-{policy_id}",
        retry_policy=retry_policy if retry_policy is not None else {},
        timeout_policy=timeout_policy,
        quota_policy=quota_policy if quota_policy is not None else {},
        enabled=enabled,
    )


class TestWorkspacePipelineExecutionPolicyService:
    def test_register_policy(self):
        service = PolicyService()

        policy = service.register(
            _policy(
                "policy-1",
                name="standard",
                retry_policy={"max_attempts": 3, "backoff_seconds": 5},
                timeout_policy=TimeoutPolicy(timeout_seconds=30, cancel_on_timeout=True, notify_on_timeout=False),
                quota_policy={"max_runtime": 50, "max_memory": 512},
            )
        )

        assert isinstance(policy, Policy)
        assert policy.enabled is True
        assert policy.retry_policy == {"max_attempts": 3, "backoff_seconds": 5}
        assert policy.timeout_policy.timeout_seconds == 30

        with pytest.raises(Error):
            service.register(None)

        with pytest.raises(Error):
            service.register(_policy("   "))

    def test_assign_unassign(self):
        service = PolicyService()
        service.register(_policy("policy-1", name="standard"))

        assignment = service.assign("pipeline-1", "policy-1")

        assert isinstance(assignment, Assignment)
        assert assignment.pipeline_id == "pipeline-1"
        assert assignment.policy_id == "policy-1"

        service.unassign("pipeline-1")

        with pytest.raises(Error):
            service.policy("pipeline-1")

        with pytest.raises(Error):
            service.unassign("pipeline-1")

    def test_effective_policy_lookup(self):
        service = PolicyService()
        service.register(_policy("policy-1", name="standard"))
        service.register(_policy("policy-2", name="lenient"))

        service.assign("pipeline-1", "policy-1")
        service.assign("pipeline-2", "policy-2")

        assert service.policy("pipeline-1").policy_id == "policy-1"
        assert service.policy("pipeline-2").policy_id == "policy-2"

        with pytest.raises(Error):
            service.policy("pipeline-without-assignment")

    def test_configuration_validation(self):
        service = PolicyService()
        service.register(_policy("policy-enabled", name="enabled-policy", enabled=True))
        service.register(_policy("policy-disabled", name="disabled-policy", enabled=False))

        service.assign("pipeline-1", "policy-enabled")
        service.assign("pipeline-2", "policy-disabled")

        assert service.validate("pipeline-1") is True
        assert service.validate("pipeline-2") is False

        with pytest.raises(Error):
            service.validate("pipeline-without-assignment")

    def test_duplicate_rejection(self):
        service = PolicyService()
        service.register(_policy("policy-1", name="standard"))

        with pytest.raises(Error):
            service.register(_policy("policy-1", name="a-different-name"))

        with pytest.raises(Error):
            service.register(_policy("policy-2", name="standard"))

    def test_conflicting_assignment_rejection(self):
        service = PolicyService()
        service.register(_policy("policy-1", name="standard"))
        service.register(_policy("policy-2", name="lenient"))

        service.assign("pipeline-1", "policy-1")

        with pytest.raises(Error):
            service.assign("pipeline-1", "policy-2")

        # re-assigning to the same policy is not a conflict
        service.assign("pipeline-1", "policy-1")

        with pytest.raises(Error):
            service.assign("pipeline-1", "unknown-policy")

    def test_validation_rejections(self):
        service = PolicyService()

        with pytest.raises(Error):
            service.assign("   ", "policy-1")

        with pytest.raises(Error):
            service.assign("pipeline-1", "   ")

        with pytest.raises(Error):
            _policy("policy-1", quota_policy={"not_a_real_key": 1})

        with pytest.raises(Error):
            _policy("policy-1", quota_policy={"max_runtime": -1})

        with pytest.raises(Error):
            Policy(policy_id="policy-1", name="x", timeout_policy="not_a_timeout_policy")

    def test_validate_integrates_with_quota_service(self):
        quota_service = QuotaService(max_runtime=10, max_memory=100, max_parallel_tasks=1)
        quota_service.register(
            Budget(budget_id="budget-1", pipeline_id="pipeline-1", max_runtime=20, max_memory=50, max_parallel_tasks=1)
        )

        policy_service = PolicyService(quota_service=quota_service)
        policy_service.register(_policy("policy-1", name="quota-checked", quota_policy={"max_runtime": 20}))
        policy_service.assign("pipeline-1", "policy-1")

        # the pipeline's budget requests more runtime than the quota pool has, so validate() fails
        assert policy_service.validate("pipeline-1") is False

        smaller_budget_service = QuotaService(max_runtime=10, max_memory=100, max_parallel_tasks=1)
        smaller_budget_service.register(
            Budget(budget_id="budget-2", pipeline_id="pipeline-2", max_runtime=5, max_memory=50, max_parallel_tasks=1)
        )

        fitting_policy_service = PolicyService(quota_service=smaller_budget_service)
        fitting_policy_service.register(_policy("policy-1", name="quota-checked", quota_policy={"max_runtime": 5}))
        fitting_policy_service.assign("pipeline-2", "policy-1")

        assert fitting_policy_service.validate("pipeline-2") is True
