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

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRecord,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_rollback_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_rollback_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackService:
    """
    Restores a consumer projection execution capability registry
    event subscription lifecycle policy profile binding preset to a
    previously recorded deployment, by recreating independent
    binding copies from the historical preset version's referenced
    binding templates, while preserving deployment history.

    The service's responsibility is orchestrating rollback, not
    deployment or history recording themselves. It does NOT deploy
    presets outside of a rollback, mutate or remove prior deployment
    records, log, or publish events. It operates over a deployment
    history service, a preset version service, a binding template
    registry, a binding registry, and an activation service supplied
    at construction time. A preset's "current" deployment is always
    its most recently recorded one.

    The service is:
    - Non-destructive: A rollback is recorded as a new, append-only
      deployment record; no prior record is ever modified or removed
    - Atomic: Every binding template referenced by the target
      version, and every source binding it is built from, is
      validated before any binding is recreated, registered, or
      activated, so a single unknown template or source binding
      fails the whole rollback, leaving no partial restoration in
      place
    - Consistent: The most recently recorded deployment is always
      treated as the preset's active deployment, so recording a
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
        preset_version_service,
        template_registry,
        binding_registry,
        activation_service,
    ):
        """
        Args:
            deployment_history_service: The service recording and
                querying preset deployment history
            preset_version_service: The service used to resolve the
                binding templates a previously deployed version
                snapshotted. Any object exposing `find(preset_id,
                version)` is accepted
            template_registry: The registry used to resolve a version
                snapshot's member binding templates. Any object
                exposing `find(template_id)`, returning an object
                with a `binding_ids` collection, is accepted
            binding_registry: The registry used to resolve a binding
                template's source bindings, and to register the
                bindings recreated for a rollback. Any object
                exposing `find(binding_id)` and `register(binding)`
                is accepted
            activation_service: The service used to activate every
                recreated binding. Any object exposing
                `activate(binding_id)` is accepted
        """

        for dependency, name in (
            (deployment_history_service, "deployment history service"),
            (preset_version_service, "preset version service"),
            (template_registry, "template registry"),
            (binding_registry, "binding registry"),
            (activation_service, "activation service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError(
                    f"Cannot initialize rollback service with a None {name}."
                )

        self._deployment_history_service = deployment_history_service
        self._preset_version_service = preset_version_service
        self._template_registry = template_registry
        self._binding_registry = binding_registry
        self._activation_service = activation_service
        self._rollback_records = {}
        self._sequence = 0
        self._lock = RLock()

    def rollback(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackResult:
        """
        Restore a preset's active deployment to the state recorded by
        a specific prior deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError:
                If the request is None, has a blank preset ID or
                deployment ID, the preset ID is unknown, no
                deployment exists under the deployment ID for that
                preset, the deployment ID is already current, or the
                target deployment's version can no longer be
                resolved to its referenced binding templates or their
                source bindings
        """

        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError(
                "Cannot roll back from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError(
                "Cannot roll back: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackRequest."
            )

        with self._lock:
            history = self._deployment_history_service.history(request.preset_id)

            if not history:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError(
                    f"Cannot roll back: preset ID {request.preset_id!r} is unknown."
                )

            target_record = next(
                (record for record in history if record.deployment_id == request.deployment_id),
                None,
            )

            if target_record is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError(
                    f"Cannot roll back: no deployment found under deployment ID {request.deployment_id!r} for preset ID {request.preset_id!r}."
                )

            current = history[-1]

            if current.deployment_id == request.deployment_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError(
                    f"Cannot roll back: deployment ID {request.deployment_id!r} is already current for preset ID {request.preset_id!r}."
                )

            version_snapshot = self._preset_version_service.find(request.preset_id, target_record.version)

            if version_snapshot is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError(
                    f"Cannot roll back: deployment history is incomplete — version {target_record.version!r} "
                    f"for preset ID {request.preset_id!r} could not be resolved."
                )

            sources_by_template = []

            for template_id in version_snapshot.template_ids:
                template = self._template_registry.find(template_id)

                if template is None:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError(
                        f"Cannot roll back: deployment history is incomplete — no binding template is registered "
                        f"under template ID {template_id!r}."
                    )

                sources = []

                for binding_id in template.binding_ids:
                    source = self._binding_registry.find(binding_id)

                    if source is None:
                        raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError(
                            f"Cannot roll back: deployment history is incomplete — no binding is registered "
                            f"under binding ID {binding_id!r}."
                        )

                    sources.append(source)

                sources_by_template.append((template_id, sources))

            restored_deployment_id = str(uuid4())

            instantiated = []

            for template_id, sources in sources_by_template:
                for source in sources:
                    self._sequence += 1

                    instance = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
                        binding_id=f"{restored_deployment_id}::{template_id}::{source.binding_id}::{self._sequence}",
                        profile_id=source.profile_id,
                        capability_id=source.capability_id,
                        created_at=datetime.now(timezone.utc),
                    )

                    self._binding_registry.register(instance)
                    self._activation_service.activate(instance.binding_id)

                    instantiated.append(instance.binding_id)

            restored_deployment = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRecord(
                deployment_id=restored_deployment_id,
                preset_id=request.preset_id,
                version=target_record.version,
                environment=target_record.environment,
                instantiated_binding_ids=tuple(instantiated),
                deployed_at=datetime.now(timezone.utc),
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentStatus.SUCCEEDED,
            )

            self._deployment_history_service.record(restored_deployment)

            self._rollback_records[request.preset_id] = self._rollback_records.get(
                request.preset_id, ()
            ) + (restored_deployment,)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackResult(
                previous_deployment=current,
                restored_deployment=restored_deployment,
                instantiated_binding_ids=tuple(instantiated),
                successful=True,
            )

    def can_rollback(self, preset_id: str) -> bool:
        """
        Check whether a preset currently has a prior deployment,
        other than its current one, to roll back to.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError:
                If preset_id is None or blank
        """

        self._validate_id(preset_id, "preset ID")

        return len(self._deployment_history_service.history(preset_id)) >= 2

    def rollback_history(self, preset_id: str) -> tuple:
        """
        List every deployment recorded for a preset, including any
        prior rollbacks, in chronological order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError:
                If preset_id is None or blank
        """

        self._validate_id(preset_id, "preset ID")

        return self._deployment_history_service.history(preset_id)

    def latest_rollback(self, preset_id: str):
        """
        Find the most recent deployment record produced by a
        rollback of a preset.

        Returns:
            The most recently restored deployment record for
            preset_id, or None if this service has never rolled it
            back

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError:
                If preset_id is None or blank
        """

        self._validate_id(preset_id, "preset ID")

        with self._lock:
            records = self._rollback_records.get(preset_id, ())

        return records[-1] if records else None

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRollbackError(
                f"Cannot roll back with an empty or blank {label}."
            )
