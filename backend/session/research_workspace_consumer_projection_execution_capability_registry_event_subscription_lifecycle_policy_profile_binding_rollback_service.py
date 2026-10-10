from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_rollback_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_rollback_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackService:
    """
    Restores a consumer projection execution capability registry
    event subscription lifecycle policy profile binding to a
    previously recorded deployment, while preserving deployment
    history and ensuring runtime consistency.

    The service's responsibility is orchestrating rollback, not
    deployment or history recording themselves. It does NOT deploy
    bindings outside of a rollback, mutate or remove prior deployment
    records, log, or publish events. It operates over a deployment
    history service supplied at construction time, since it already
    carries the append-only record of every deployment. A binding's
    "current" deployment is always its most recently recorded one.

    The service is:
    - Non-destructive: A rollback is recorded as a new, append-only
      deployment record; no prior record is ever modified or removed
    - Consistent: The most recently recorded deployment is always
      treated as the binding's active deployment, so recording a
      restored deployment atomically makes it current
    """

    def __init__(self, deployment_history_service):
        """
        Args:
            deployment_history_service: The service recording and
                querying binding deployment history
        """

        if deployment_history_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError(
                "Cannot initialize rollback service with a None deployment history service."
            )

        self._deployment_history_service = deployment_history_service

    def rollback(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackResult:
        """
        Restore a binding's active deployment to the state recorded
        by a specific prior deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError:
                If the request is None, has a blank binding ID or
                deployment ID, the binding ID is unknown, no
                deployment exists under the deployment ID for that
                binding, or the deployment ID is already current
        """

        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError(
                "Cannot roll back from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError(
                "Cannot roll back: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackRequest."
            )

        history = self._deployment_history_service.history(request.binding_id)

        if not history:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError(
                f"Cannot roll back: binding ID {request.binding_id!r} is unknown."
            )

        target_record = next(
            (record for record in history if record.deployment_id == request.deployment_id),
            None,
        )

        if target_record is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError(
                f"Cannot roll back: no deployment found under deployment ID {request.deployment_id!r} for binding ID {request.binding_id!r}."
            )

        current = history[-1]

        if current.deployment_id == request.deployment_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError(
                f"Cannot roll back: deployment ID {request.deployment_id!r} is already current for binding ID {request.binding_id!r}."
            )

        restored_deployment = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRecord(
            deployment_id=str(uuid4()),
            binding_id=request.binding_id,
            environment=target_record.environment,
            version=target_record.version,
            deployed_at=datetime.now(timezone.utc),
            status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentStatus.SUCCEEDED,
        )

        self._deployment_history_service.record(restored_deployment)

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackResult(
            previous_deployment=current,
            restored_deployment=restored_deployment,
            successful=True,
        )

    def can_rollback(self, binding_id: str) -> bool:
        """
        Check whether a binding currently has a prior deployment,
        other than its current one, to roll back to.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError:
                If binding_id is None or blank
        """

        self._validate_id(binding_id, "binding ID")

        return len(self._deployment_history_service.history(binding_id)) >= 2

    def rollback_history(self, binding_id: str) -> tuple:
        """
        List every deployment recorded for a binding, including any
        prior rollbacks, in chronological order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError:
                If binding_id is None or blank
        """

        self._validate_id(binding_id, "binding ID")

        return self._deployment_history_service.history(binding_id)

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRollbackError(
                f"Cannot roll back with an empty or blank {label}."
            )
