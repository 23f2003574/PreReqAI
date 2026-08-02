from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from types import MappingProxyType

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRecord,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_rollback_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_rollback_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackService:
    """
    Restores a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace to
    a previously recorded deployment, recovering the entire workspace
    state — every referenced binding, binding template, binding
    preset, and binding group — in one operation.

    The service's responsibility is orchestrating rollback, not
    deployment or history recording themselves. It does NOT deploy
    workspaces outside of a rollback, mutate or remove prior
    deployment records, log, or publish events. It operates over a
    deployment history service and the four resource registries
    supplied at construction time. A workspace's "current" deployment
    is always its most recently recorded one.

    The service is:
    - Non-destructive: A rollback is recorded as a new, append-only
      deployment record; no prior record is ever modified or removed
    - Atomic: Every resource referenced by the target deployment
      record is validated as still registered before any restored
      deployment record is committed, so a single unknown reference
      fails the whole rollback, leaving no partial restoration in
      place
    - Consistent: The most recently recorded deployment is always
      treated as the workspace's active deployment, so recording a
      restored deployment atomically makes it current
    - Idempotent: Rolling back to the deployment that is already
      current is rejected rather than repeated, so a target can only
      ever be restored once until a later deployment supersedes it
    """

    def __init__(
        self,
        deployment_history_service,
        binding_registry,
        template_registry,
        preset_registry,
        group_registry,
    ):
        """
        Args:
            deployment_history_service: The service recording and
                querying workspace deployment history. Any object
                exposing `history(workspace_id)` and `record(record)`
                is accepted
            binding_registry: The registry used to verify that a
                restored binding is still registered. Any object
                exposing `find(binding_id)` is accepted
            template_registry: The registry used to verify that a
                restored binding template is still registered. Any
                object exposing `find(template_id)` is accepted
            preset_registry: The registry used to verify that a
                restored binding preset is still registered. Any
                object exposing `find(preset_id)` is accepted
            group_registry: The registry used to verify that a
                restored binding group is still registered. Any
                object exposing `find(group_id)` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError:
                If any dependency is None
        """

        for dependency, name in (
            (deployment_history_service, "deployment history service"),
            (binding_registry, "binding registry"),
            (template_registry, "binding template registry"),
            (preset_registry, "binding preset registry"),
            (group_registry, "binding group registry"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError(
                    f"Cannot initialize rollback service with a None {name}."
                )

        self._deployment_history_service = deployment_history_service
        self._binding_registry = binding_registry
        self._template_registry = template_registry
        self._preset_registry = preset_registry
        self._group_registry = group_registry
        self._rollback_records = {}
        self._lock = RLock()

    def rollback(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackResult:
        """
        Restore a workspace's active deployment to the state recorded
        by a specific prior deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError:
                If the request is None, has a blank workspace ID or
                deployment ID, the workspace ID is unknown, no
                deployment exists under the deployment ID for that
                workspace, the deployment ID is already current, or
                the target deployment's resources can no longer be
                resolved in their registries
        """

        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError(
                "Cannot roll back from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError(
                "Cannot roll back: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackRequest."
            )

        with self._lock:
            history = self._deployment_history_service.history(request.workspace_id)

            if not history:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError(
                    f"Cannot roll back: workspace ID {request.workspace_id!r} is unknown."
                )

            target_record = next(
                (record for record in history if record.deployment_id == request.deployment_id),
                None,
            )

            if target_record is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError(
                    f"Cannot roll back: no deployment found under deployment ID {request.deployment_id!r} for workspace ID {request.workspace_id!r}."
                )

            current = history[-1]

            if current.deployment_id == request.deployment_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError(
                    f"Cannot roll back: deployment ID {request.deployment_id!r} is already current for workspace ID {request.workspace_id!r}."
                )

            restored_resources = {}

            for kind, label, registry in (
                ("bindings", "binding", self._binding_registry),
                ("templates", "binding template", self._template_registry),
                ("presets", "binding preset", self._preset_registry),
                ("groups", "binding group", self._group_registry),
            ):
                member_ids = target_record.deployed_resources.get(kind, ())

                for member_id in member_ids:
                    if registry.find(member_id) is None:
                        raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError(
                            f"Cannot roll back: deployment history is incomplete — no {label} is registered "
                            f"under ID {member_id!r}."
                        )

                restored_resources[kind] = tuple(member_ids)

            restored_deployment = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRecord(
                deployment_id=str(uuid4()),
                workspace_id=request.workspace_id,
                version=target_record.version,
                environment=target_record.environment,
                deployed_resources=MappingProxyType(restored_resources),
                deployed_at=datetime.now(timezone.utc),
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentStatus.SUCCEEDED,
            )

            self._deployment_history_service.record(restored_deployment)

            self._rollback_records[request.workspace_id] = self._rollback_records.get(
                request.workspace_id, ()
            ) + (restored_deployment,)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackResult(
                previous_deployment=current,
                restored_deployment=restored_deployment,
                restored_resources=MappingProxyType(restored_resources),
                successful=True,
            )

    def can_rollback(self, workspace_id: str) -> bool:
        """
        Check whether a workspace currently has a prior deployment,
        other than its current one, to roll back to.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError:
                If workspace_id is None or blank
        """

        self._validate_id(workspace_id, "workspace ID")

        return len(self._deployment_history_service.history(workspace_id)) >= 2

    def rollback_history(self, workspace_id: str) -> tuple:
        """
        List every deployment recorded for a workspace, including any
        prior rollbacks, in chronological order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError:
                If workspace_id is None or blank
        """

        self._validate_id(workspace_id, "workspace ID")

        return self._deployment_history_service.history(workspace_id)

    def latest_rollback(self, workspace_id: str):
        """
        Find the most recent deployment record produced by a rollback
        of a workspace.

        Returns:
            The most recently restored deployment record for
            workspace_id, or None if this service has never rolled it
            back

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError:
                If workspace_id is None or blank
        """

        self._validate_id(workspace_id, "workspace ID")

        with self._lock:
            records = self._rollback_records.get(workspace_id, ())

        return records[-1] if records else None

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRollbackError(
                f"Cannot roll back with an empty or blank {label}."
            )
