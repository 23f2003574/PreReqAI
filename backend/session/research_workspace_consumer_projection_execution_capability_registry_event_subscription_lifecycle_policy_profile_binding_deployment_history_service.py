from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_deployment_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_deployment_history_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryService:
    """
    Records and queries the deployment history of consumer
    projection execution capability registry event subscription
    lifecycle policy profile bindings, for auditing, rollback, and
    operational analysis.

    The service's responsibility is recording and read-only
    querying, not deployment itself, binding creation, or
    activation. It does NOT deploy bindings, create bindings,
    activate or deactivate bindings, mutate a recorded record,
    persist history externally, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two records may share a deployment ID
    - Chronological: Records are listed in the order they were
      recorded
    - Append-only: Records are never replaced or removed once
      recorded
    """

    def __init__(self):
        self._history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistory(
            records=()
        )

        self._lock = RLock()

    def record(
        self,
        deployment_record: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord,
    ) -> None:
        """
        Record a deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError:
                If the record is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord,
                has a blank deployment ID, binding ID, environment, or
                version, has an unknown status, or its deployment ID
                has already been recorded
        """

        self._validate_record(deployment_record)

        with self._lock:
            if any(
                existing.deployment_id == deployment_record.deployment_id
                for existing in self._history.records
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError(
                    f"Cannot record a deployment: deployment ID {deployment_record.deployment_id!r} has already been recorded."
                )

            self._history = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistory(
                records=self._history.records + (deployment_record,)
            )

    def find(self, deployment_id: str):
        """
        Find the record for a deployment ID.

        Returns:
            The matching deployment record, or None if no deployment
            with that ID has been recorded
        """

        with self._lock:
            for existing in self._history.records:
                if existing.deployment_id == deployment_id:
                    return existing

            return None

    def history(self, binding_id: str) -> tuple:
        """
        List every recorded deployment for a binding, in
        chronological order.
        """

        with self._lock:
            return tuple(
                record for record in self._history.records if record.binding_id == binding_id
            )

    def history_for_environment(self, environment: str) -> tuple:
        """
        List every recorded deployment for a runtime environment, in
        chronological order.
        """

        with self._lock:
            return tuple(
                record for record in self._history.records if record.environment == environment
            )

    def latest(self, binding_id: str):
        """
        Find the most recently recorded deployment for a binding.

        Returns:
            The most recent deployment record for binding_id, or None
            if no deployment has ever been recorded for it
        """

        matching = self.history(binding_id)

        return matching[-1] if matching else None

    def _validate_record(self, record) -> None:
        if record is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError(
                "Cannot record a None deployment record."
            )

        if not isinstance(
            record,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError(
                "Cannot record a deployment: record must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord."
            )

        if record.deployment_id is None or not record.deployment_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError(
                "Cannot record a deployment with an empty or blank deployment ID."
            )

        if record.binding_id is None or not record.binding_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError(
                "Cannot record a deployment with an empty or blank binding ID."
            )

        if record.environment is None or not record.environment.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError(
                "Cannot record a deployment with an empty or blank environment."
            )

        if record.version is None or not record.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError(
                "Cannot record a deployment with an empty or blank version."
            )

        if not isinstance(
            record.status,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentStatus,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentHistoryError(
                f"Cannot record a deployment with an unknown status {record.status!r}."
            )
