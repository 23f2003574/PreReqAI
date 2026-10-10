from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from types import MappingProxyType

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_execution_context import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContext,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_execution_context_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_context_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineContextSnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineContextService:
    """
    Gives consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    pipeline stages a shared key/value execution context, so state
    produced by one stage can be read by a later stage without either
    stage knowing about the other, and checkpoints that state so it
    can be restored later.

    The service's responsibility is context bookkeeping, not running
    a pipeline itself. It does NOT execute stages or pipelines;
    whoever runs a pipeline (for example, a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace execution pipeline service) is
    expected to call create() before it starts, put() and get() from
    within its stage executors, and snapshot() or restore() around
    checkpoints.

    Behavior:
    - A pipeline may have at most one active execution context; a new
      one may be created once the old one is removed
    - Every context starts with empty variables and metadata
    - A snapshot captures a context's variables and metadata at the
      moment it is taken; once constructed, a snapshot never changes,
      even as the context it was taken from continues to change
    - restore() overwrites a context's current variables and metadata
      with a snapshot's captured state; it does not revive a context
      that has been removed

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._contexts = {}
        self._context_id_by_pipeline = {}
        self._snapshots = {}
        self._lock = RLock()

    def create(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContext:
        """
        Create a new, empty execution context for a pipeline.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError:
                If pipeline_id is None or blank, or the pipeline
                already has an active execution context
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            if pipeline_id in self._context_id_by_pipeline:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                    f"Cannot create an execution context: pipeline ID {pipeline_id!r} already has an active "
                    "context."
                )

            context = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContext(
                context_id=str(uuid4()),
                pipeline_id=pipeline_id,
                variables=MappingProxyType({}),
                metadata=MappingProxyType({}),
            )

            self._contexts[context.context_id] = context
            self._context_id_by_pipeline[pipeline_id] = context.context_id

            return context

    def get(self, context_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContext:
        """
        Look up a context's current state.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError:
                If context_id is None or blank, or no context is
                registered under it
        """

        self._validate_id(context_id, "context ID")

        with self._lock:
            return self._resolve_context(context_id)

    def put(self, context_id: str, key: str, value) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContext:
        """
        Set a single shared variable on a context.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError:
                If context_id is None or blank, no context is
                registered under it, or key is not a non-blank,
                identifier-shaped string
        """

        self._validate_id(context_id, "context ID")
        self._validate_key(key)

        with self._lock:
            context = self._resolve_context(context_id)

            updated_variables = dict(context.variables)
            updated_variables[key] = value

            updated = replace(context, variables=MappingProxyType(updated_variables))
            self._contexts[context_id] = updated

            return updated

    def snapshot(self, context_id: str, stage_id: str = None) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineContextSnapshot:
        """
        Capture a context's current variables and metadata as an
        immutable checkpoint.

        Args:
            context_id: The context to capture
            stage_id: The stage triggering the checkpoint, if known

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError:
                If context_id is None or blank, or no context is
                registered under it
        """

        self._validate_id(context_id, "context ID")

        with self._lock:
            context = self._resolve_context(context_id)

            snapshot = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineContextSnapshot(
                snapshot_id=str(uuid4()),
                context_id=context_id,
                stage_id=stage_id,
                created_at=datetime.now(timezone.utc),
                variables=context.variables,
                metadata=context.metadata,
            )

            self._snapshots[snapshot.snapshot_id] = snapshot

            return snapshot

    def restore(self, snapshot_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContext:
        """
        Overwrite a context's variables and metadata with a
        snapshot's captured state.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError:
                If snapshot_id is None or blank, no snapshot is
                registered under it, or the snapshot's context no
                longer exists
        """

        self._validate_id(snapshot_id, "snapshot ID")

        with self._lock:
            snapshot = self._snapshots.get(snapshot_id)

            if snapshot is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                    f"No pipeline context snapshot is registered under snapshot ID {snapshot_id!r}."
                )

            current = self._contexts.get(snapshot.context_id)

            if current is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                    f"Cannot restore snapshot ID {snapshot_id!r}: context ID {snapshot.context_id!r} no "
                    "longer exists."
                )

            restored = replace(current, variables=snapshot.variables, metadata=snapshot.metadata)
            self._contexts[snapshot.context_id] = restored

            return restored

    def remove(self, context_id: str) -> None:
        """
        Remove a context.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError:
                If context_id is None or blank, or no context is
                registered under it
        """

        self._validate_id(context_id, "context ID")

        with self._lock:
            context = self._resolve_context(context_id)

            del self._contexts[context_id]
            del self._context_id_by_pipeline[context.pipeline_id]

    def _resolve_context(self, context_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContext:
        context = self._contexts.get(context_id)

        if context is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                f"No pipeline execution context is registered under context ID {context_id!r}."
            )

        return context

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                f"Cannot operate with an empty or blank {label}."
            )

    def _validate_key(self, key: str) -> None:
        if not isinstance(key, str) or not key.strip() or not key.isidentifier():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionContextError(
                f"Invalid pipeline execution context variable key {key!r}; keys must be non-blank, "
                "identifier-shaped strings."
            )
