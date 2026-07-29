from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRecord,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_rollback_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_rollback_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackService:
    """
    Restores a consumer projection execution capability registry
    event subscription lifecycle policy profile binding group to a
    previously recorded deployment, while preserving deployment
    history and ensuring every member binding reverts together.

    The service's responsibility is orchestrating rollback, not
    deployment or history recording themselves. It does NOT deploy
    groups outside of a rollback, mutate or remove prior deployment
    records, log, or publish events. It operates over a deployment
    history service and a group version service supplied at
    construction time. A group's "current" deployment is always its
    most recently recorded one.

    The service is:
    - Non-destructive: A rollback is recorded as a new, append-only
      deployment record; no prior record is ever modified or removed
    - Atomic: The bindings restored by a rollback are always the
      complete member set snapshotted by the target deployment's
      version, restored together as a single unit
    - Consistent: The most recently recorded deployment is always
      treated as the group's active deployment, so recording a
      restored deployment atomically makes it current
    - Idempotent: Rolling back to the deployment that is already
      current is rejected rather than repeated, so a target can only
      ever be restored once until a later deployment supersedes it
    """

    def __init__(self, deployment_history_service, group_version_service):
        """
        Args:
            deployment_history_service: The service recording and
                querying group deployment history
            group_version_service: The service used to resolve the
                member bindings a previously deployed version
                snapshotted. Any object exposing `find(group_id,
                version)` is accepted
        """

        if deployment_history_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                "Cannot initialize rollback service with a None deployment history service."
            )

        if group_version_service is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                "Cannot initialize rollback service with a None group version service."
            )

        self._deployment_history_service = deployment_history_service
        self._group_version_service = group_version_service
        self._rollback_records = {}
        self._lock = RLock()

    def rollback(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackResult:
        """
        Restore a group's active deployment to the state recorded by
        a specific prior deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError:
                If the request is None, has a blank group ID or
                deployment ID, the group ID is unknown, no deployment
                exists under the deployment ID for that group, the
                deployment ID is already current, or the target
                deployment's version can no longer be resolved to its
                member bindings
        """

        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                "Cannot roll back from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                "Cannot roll back: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackRequest."
            )

        with self._lock:
            history = self._deployment_history_service.history(request.group_id)

            if not history:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                    f"Cannot roll back: group ID {request.group_id!r} is unknown."
                )

            target_record = next(
                (record for record in history if record.deployment_id == request.deployment_id),
                None,
            )

            if target_record is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                    f"Cannot roll back: no deployment found under deployment ID {request.deployment_id!r} for group ID {request.group_id!r}."
                )

            current = history[-1]

            if current.deployment_id == request.deployment_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                    f"Cannot roll back: deployment ID {request.deployment_id!r} is already current for group ID {request.group_id!r}."
                )

            version_snapshot = self._group_version_service.find(request.group_id, target_record.version)

            if version_snapshot is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                    f"Cannot roll back: deployment history is incomplete — version {target_record.version!r} "
                    f"for group ID {request.group_id!r} could not be resolved."
                )

            restored_deployment = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRecord(
                deployment_id=str(uuid4()),
                group_id=request.group_id,
                version=target_record.version,
                environment=target_record.environment,
                deployed_at=datetime.now(timezone.utc),
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentStatus.SUCCEEDED,
            )

            self._deployment_history_service.record(restored_deployment)

            self._rollback_records[request.group_id] = self._rollback_records.get(
                request.group_id, ()
            ) + (restored_deployment,)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackResult(
                previous_deployment=current,
                restored_deployment=restored_deployment,
                restored_bindings=version_snapshot.binding_ids,
                successful=True,
            )

    def can_rollback(self, group_id: str) -> bool:
        """
        Check whether a group currently has a prior deployment, other
        than its current one, to roll back to.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError:
                If group_id is None or blank
        """

        self._validate_id(group_id, "group ID")

        return len(self._deployment_history_service.history(group_id)) >= 2

    def rollback_history(self, group_id: str) -> tuple:
        """
        List every deployment recorded for a group, including any
        prior rollbacks, in chronological order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError:
                If group_id is None or blank
        """

        self._validate_id(group_id, "group ID")

        return self._deployment_history_service.history(group_id)

    def latest_rollback(self, group_id: str):
        """
        Find the most recent deployment record produced by a rollback
        of a group.

        Returns:
            The most recently restored deployment record for
            group_id, or None if this service has never rolled it
            back

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError:
                If group_id is None or blank
        """

        self._validate_id(group_id, "group ID")

        with self._lock:
            records = self._rollback_records.get(group_id, ())

        return records[-1] if records else None

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRollbackError(
                f"Cannot roll back with an empty or blank {label}."
            )
