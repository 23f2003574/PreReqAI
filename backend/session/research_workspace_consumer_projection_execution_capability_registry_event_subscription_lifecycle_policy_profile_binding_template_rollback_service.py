from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRecord,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_rollback_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_rollback_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackService:
    """
    Restores a consumer projection execution capability registry
    event subscription lifecycle policy profile binding template to
    a previously recorded deployment, by recreating independent
    binding copies from the historical template version the target
    deployment snapshotted, while preserving deployment history.

    The service's responsibility is orchestrating rollback, not
    deployment or history recording themselves. It does NOT deploy
    templates outside of a rollback, mutate or remove prior
    deployment records, log, or publish events. It operates over a
    deployment history service, a template version service, a
    binding registry, and an activation service supplied at
    construction time. A template's "current" deployment is always
    its most recently recorded one.

    The service is:
    - Non-destructive: A rollback is recorded as a new, append-only
      deployment record; no prior record is ever modified or removed
    - Atomic: Every source binding referenced by the target version is
      validated before any binding is recreated, registered, or
      activated, so a single unknown source binding fails the whole
      rollback, leaving no partial restoration in place
    - Consistent: The most recently recorded deployment is always
      treated as the template's active deployment, so recording a
      restored deployment atomically makes it current
    - Idempotent: Rolling back to the deployment that is already
      current is rejected rather than repeated, so a target can only
      ever be restored once until a later deployment supersedes it
    - Copy-independent: Every rollback recreates brand-new binding
      records; no recreated binding is shared between rollbacks or
      with the source bindings the target version was built from
    """

    def __init__(
        self,
        deployment_history_service,
        template_version_service,
        binding_registry,
        activation_service,
    ):
        """
        Args:
            deployment_history_service: The service recording and
                querying template deployment history
            template_version_service: The service used to resolve the
                source bindings a previously deployed version
                snapshotted. Any object exposing `find(template_id,
                version)` is accepted
            binding_registry: The registry used to resolve a version
                snapshot's source bindings, and to register the
                bindings recreated for a rollback. Any object exposing
                `find(binding_id)` and `register(binding)` is accepted
            activation_service: The service used to activate every
                recreated binding. Any object exposing
                `activate(binding_id)` is accepted
        """

        for dependency, name in (
            (deployment_history_service, "deployment history service"),
            (template_version_service, "template version service"),
            (binding_registry, "binding registry"),
            (activation_service, "activation service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                    f"Cannot initialize rollback service with a None {name}."
                )

        self._deployment_history_service = deployment_history_service
        self._template_version_service = template_version_service
        self._binding_registry = binding_registry
        self._activation_service = activation_service
        self._rollback_records = {}
        self._sequence = 0
        self._lock = RLock()

    def rollback(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackResult:
        """
        Restore a template's active deployment to the state recorded
        by a specific prior deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError:
                If the request is None, has a blank template ID or
                deployment ID, the template ID is unknown, no
                deployment exists under the deployment ID for that
                template, the deployment ID is already current, or
                the target deployment's version can no longer be
                resolved to its source bindings
        """

        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                "Cannot roll back from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                "Cannot roll back: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackRequest."
            )

        with self._lock:
            history = self._deployment_history_service.history(request.template_id)

            if not history:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                    f"Cannot roll back: template ID {request.template_id!r} is unknown."
                )

            target_record = next(
                (record for record in history if record.deployment_id == request.deployment_id),
                None,
            )

            if target_record is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                    f"Cannot roll back: no deployment found under deployment ID {request.deployment_id!r} for template ID {request.template_id!r}."
                )

            current = history[-1]

            if current.deployment_id == request.deployment_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                    f"Cannot roll back: deployment ID {request.deployment_id!r} is already current for template ID {request.template_id!r}."
                )

            version_snapshot = self._template_version_service.find(request.template_id, target_record.version)

            if version_snapshot is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                    f"Cannot roll back: deployment history is incomplete — version {target_record.version!r} "
                    f"for template ID {request.template_id!r} could not be resolved."
                )

            sources = []

            for binding_id in version_snapshot.binding_ids:
                source = self._binding_registry.find(binding_id)

                if source is None:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                        f"Cannot roll back: deployment history is incomplete — no binding is registered "
                        f"under binding ID {binding_id!r}."
                    )

                sources.append(source)

            restored_deployment_id = str(uuid4())

            instantiated = []

            for source in sources:
                self._sequence += 1

                instance = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
                    binding_id=f"{restored_deployment_id}::{source.binding_id}::{self._sequence}",
                    profile_id=source.profile_id,
                    capability_id=source.capability_id,
                    created_at=datetime.now(timezone.utc),
                )

                self._binding_registry.register(instance)
                self._activation_service.activate(instance.binding_id)

                instantiated.append(instance.binding_id)

            restored_deployment = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRecord(
                deployment_id=restored_deployment_id,
                template_id=request.template_id,
                version=target_record.version,
                environment=target_record.environment,
                instantiated_binding_ids=tuple(instantiated),
                deployed_at=datetime.now(timezone.utc),
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentStatus.SUCCEEDED,
            )

            self._deployment_history_service.record(restored_deployment)

            self._rollback_records[request.template_id] = self._rollback_records.get(
                request.template_id, ()
            ) + (restored_deployment,)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackResult(
                previous_deployment=current,
                restored_deployment=restored_deployment,
                instantiated_binding_ids=tuple(instantiated),
                successful=True,
            )

    def can_rollback(self, template_id: str) -> bool:
        """
        Check whether a template currently has a prior deployment,
        other than its current one, to roll back to.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError:
                If template_id is None or blank
        """

        self._validate_id(template_id, "template ID")

        return len(self._deployment_history_service.history(template_id)) >= 2

    def rollback_history(self, template_id: str) -> tuple:
        """
        List every deployment recorded for a template, including any
        prior rollbacks, in chronological order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError:
                If template_id is None or blank
        """

        self._validate_id(template_id, "template ID")

        return self._deployment_history_service.history(template_id)

    def latest_rollback(self, template_id: str):
        """
        Find the most recent deployment record produced by a rollback
        of a template.

        Returns:
            The most recently restored deployment record for
            template_id, or None if this service has never rolled it
            back

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError:
                If template_id is None or blank
        """

        self._validate_id(template_id, "template ID")

        with self._lock:
            records = self._rollback_records.get(template_id, ())

        return records[-1] if records else None

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRollbackError(
                f"Cannot roll back with an empty or blank {label}."
            )
