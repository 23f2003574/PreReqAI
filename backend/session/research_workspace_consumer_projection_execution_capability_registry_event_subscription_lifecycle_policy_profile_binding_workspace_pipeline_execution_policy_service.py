from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_policy_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePolicyAssignment,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_execution_policy_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_execution_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicy,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyService:
    """
    Lets administrators register reusable consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace execution policies and assign
    them to pipelines, so retry, timeout, and quota behavior can be
    configured and reused without changing any pipeline's own
    definition.

    The service's responsibility is registration, assignment, and
    pre-execution validation, not enforcement. It does NOT execute
    pipelines, retry a stage, enforce a timeout, or reserve a quota
    itself; whoever runs a pipeline is expected to call validate()
    before starting it, and to apply the resolved policy's
    retry_policy, timeout_policy, and quota_policy using the existing
    retry, timeout, and quota services.

    Behavior:
    - A policy's name must be unique among registered policies, so an
      administrator can never register two policies that look alike
    - A policy may be assigned to any number of pipelines; a pipeline
      may have at most one assignment at a time
    - Reassigning a pipeline to a policy it is not currently assigned
      to is rejected as conflicting; the caller must unassign() first
    - validate() reports whether a pipeline's effective policy
      currently allows it to run: disabled policies fail validation,
      and, when a quota service was supplied at construction and the
      policy configures a quota_policy, so does an exceeded quota

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, quota_service=None):
        """
        Args:
            quota_service: An optional consumer projection execution
                capability registry event subscription lifecycle
                policy profile binding workspace pipeline quota
                service. When given, validate() additionally checks
                a quota-policy-configured pipeline's assigned budget
                against it. Any object exposing
                `validate(pipeline_id)`, returning an object with an
                `accepted` attribute, is accepted
        """

        self._quota_service = quota_service
        self._policies_by_id = {}
        self._policy_id_by_name = {}
        self._assignment_by_pipeline = {}
        self._lock = RLock()

    def register(self, policy: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicy) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicy:
        """
        Register a reusable execution policy.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError:
                If policy is None or not a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicy, its policy ID is
                already registered, or its name is already used by
                another registered policy
        """

        if policy is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                "Cannot register a None pipeline execution policy."
            )

        if not isinstance(policy, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicy):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                "Cannot register a pipeline execution policy: policy must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicy."
            )

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                    f"Policy ID {policy.policy_id!r} is already registered."
                )

            if policy.name in self._policy_id_by_name:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                    f"Policy name {policy.name!r} is already used by policy ID "
                    f"{self._policy_id_by_name[policy.name]!r}."
                )

            self._policies_by_id[policy.policy_id] = policy
            self._policy_id_by_name[policy.name] = policy.policy_id

            return policy

    def assign(self, pipeline_id: str, policy_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePolicyAssignment:
        """
        Assign a registered policy to a pipeline.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError:
                If pipeline_id or policy_id is None or blank, no
                policy is registered under policy_id, or the pipeline
                is already assigned to a different policy
        """

        self._validate_id(pipeline_id, "pipeline ID")
        self._validate_id(policy_id, "policy ID")

        with self._lock:
            if policy_id not in self._policies_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                    f"No pipeline execution policy is registered under policy ID {policy_id!r}."
                )

            existing = self._assignment_by_pipeline.get(pipeline_id)

            if existing is not None and existing.policy_id != policy_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                    f"Cannot assign policy ID {policy_id!r} to pipeline ID {pipeline_id!r}: it is already "
                    f"assigned to policy ID {existing.policy_id!r}. Unassign it first."
                )

            assignment = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePolicyAssignment(pipeline_id=pipeline_id, policy_id=policy_id)
            self._assignment_by_pipeline[pipeline_id] = assignment

            return assignment

    def unassign(self, pipeline_id: str) -> None:
        """
        Remove a pipeline's policy assignment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError:
                If pipeline_id is None or blank, or the pipeline has
                no active assignment
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            if pipeline_id not in self._assignment_by_pipeline:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                    f"Pipeline ID {pipeline_id!r} has no active policy assignment."
                )

            del self._assignment_by_pipeline[pipeline_id]

    def policy(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicy:
        """
        Look up a pipeline's currently effective policy.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError:
                If pipeline_id is None or blank, or the pipeline has
                no active assignment
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            return self._resolve_policy(pipeline_id)

    def validate(self, pipeline_id: str) -> bool:
        """
        Check whether a pipeline's effective policy currently allows
        it to run.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError:
                If pipeline_id is None or blank, or the pipeline has
                no active assignment
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            policy = self._resolve_policy(pipeline_id)

            if not policy.enabled:
                return False

            if self._quota_service is not None and policy.quota_policy:
                quota_result = self._quota_service.validate(pipeline_id)

                if not quota_result.accepted:
                    return False

            return True

    def _resolve_policy(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicy:
        assignment = self._assignment_by_pipeline.get(pipeline_id)

        if assignment is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                f"Pipeline ID {pipeline_id!r} has no active policy assignment."
            )

        return self._policies_by_id[assignment.policy_id]

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                f"Cannot operate with an empty or blank {label}."
            )
