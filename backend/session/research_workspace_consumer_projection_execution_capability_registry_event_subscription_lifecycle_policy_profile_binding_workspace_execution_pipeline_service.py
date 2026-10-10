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

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_pipeline_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_pipeline import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_event import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEvent,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_pipeline_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService:
    """
    Orchestrates a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution pipeline's stages — typically validation, review,
    merge, and deployment — running each in ascending order against
    the executor configured for its type.

    The service's responsibility is sequencing, checkpointing, and
    lifecycle control, not performing the operations a stage
    represents. It does NOT validate, review, merge, or deploy
    anything itself; it dispatches each stage to the executor
    registered for the stage's type. This is how it integrates with
    the existing validation, review, merge, and deployment services:
    a caller binds their real `validate`, `submit`/`approve`, `merge`,
    and `deploy` methods into the stage executor mapping this service
    is constructed with, rather than this service depending on their
    concrete implementations.

    Behavior:
    - Stages run sequentially, in ascending order
    - Progress is checkpointed after every successful stage, so
      pausing, cancelling, or failing partway through preserves
      exactly how far the pipeline got, and resuming continues from
      there rather than from the start
    - A pipeline stops immediately on the first stage failure or
      cancellation; later stages never run
    - pause() and cancel() take effect at the next stage boundary. A
      stage executor may call back into pause() or cancel() on the
      pipeline it is running as part of its own logic; the request is
      honored as soon as that stage finishes. Called from another
      thread while a pipeline is running, they block until that run
      reaches its next boundary

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, stage_executors=None, event_bus=None):
        """
        Args:
            stage_executors: A mapping from stage type ("validation",
                "review", "merge", "deployment") to a callable
                accepting (workspace_id, configuration) that performs
                the stage. A stage type used by a pipeline but absent
                from this mapping fails the stage when it runs
            event_bus: An optional consumer projection execution
                capability registry event subscription lifecycle
                policy profile binding workspace pipeline event bus.
                When given, a "stage_completed" event is published to
                it after every stage that finishes successfully
        """

        self._stage_executors = dict(stage_executors) if stage_executors else {}
        self._event_bus = event_bus
        self._pipelines = {}
        self._progress = {}
        self._control = {}
        self._lock = RLock()

    def create(
        self,
        pipeline: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline:
        """
        Register a new execution pipeline in the CREATED state.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError:
                If pipeline is None or not a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage, or its pipeline ID is
                already registered
        """

        if pipeline is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                "Cannot create a None execution pipeline."
            )

        if not isinstance(pipeline, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                "Cannot create an execution pipeline: pipeline must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline."
            )

        with self._lock:
            if pipeline.pipeline_id in self._pipelines:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                    f"Pipeline ID {pipeline.pipeline_id!r} is already registered."
                )

            created = replace(pipeline, status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.CREATED)

            self._pipelines[pipeline.pipeline_id] = created
            self._progress[pipeline.pipeline_id] = 0
            self._control[pipeline.pipeline_id] = {"pause_requested": False, "cancel_requested": False}

            return created

    def execute(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline:
        """
        Run a CREATED pipeline's stages from the beginning.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError:
                If pipeline_id is None or blank, no pipeline is
                registered under it, or the pipeline is not CREATED
        """

        self._validate_id(pipeline_id)

        with self._lock:
            pipeline = self._resolve(pipeline_id)

            if pipeline.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.CREATED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                    f"Cannot execute pipeline ID {pipeline_id!r}: pipeline is {pipeline.status.value}, not "
                    "created. Use resume() to continue a paused pipeline."
                )

        return self._run(pipeline_id)

    def pause(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline:
        """
        Request that a running pipeline pause at its next stage
        boundary.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError:
                If pipeline_id is None or blank, no pipeline is
                registered under it, or the pipeline is not RUNNING
        """

        self._validate_id(pipeline_id)

        with self._lock:
            pipeline = self._resolve(pipeline_id)

            if pipeline.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.RUNNING:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                    f"Cannot pause pipeline ID {pipeline_id!r}: pipeline is {pipeline.status.value}, not running."
                )

            self._control[pipeline_id]["pause_requested"] = True

            return pipeline

    def resume(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline:
        """
        Continue a PAUSED pipeline's stages from its last checkpoint.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError:
                If pipeline_id is None or blank, no pipeline is
                registered under it, or the pipeline is not PAUSED
        """

        self._validate_id(pipeline_id)

        with self._lock:
            pipeline = self._resolve(pipeline_id)

            if pipeline.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.PAUSED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                    f"Cannot resume pipeline ID {pipeline_id!r}: pipeline is {pipeline.status.value}, not paused."
                )

        return self._run(pipeline_id)

    def cancel(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline:
        """
        Cancel a pipeline that has not yet finished.

        A CREATED or PAUSED pipeline is cancelled immediately. A
        RUNNING pipeline is cancelled at its next stage boundary.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError:
                If pipeline_id is None or blank, no pipeline is
                registered under it, or the pipeline has already
                COMPLETED, FAILED, or been CANCELLED
        """

        self._validate_id(pipeline_id)

        with self._lock:
            pipeline = self._resolve(pipeline_id)

            if pipeline.status not in (ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.CREATED, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.RUNNING, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.PAUSED):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                    f"Cannot cancel pipeline ID {pipeline_id!r}: pipeline is already {pipeline.status.value}."
                )

            if pipeline.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.RUNNING:
                self._control[pipeline_id]["cancel_requested"] = True

                return pipeline

            cancelled = replace(pipeline, status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.CANCELLED)

            self._pipelines[pipeline_id] = cancelled

            return cancelled

    def status(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline:
        """
        Look up a pipeline's current state.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError:
                If pipeline_id is None or blank, or no pipeline is
                registered under it
        """

        self._validate_id(pipeline_id)

        with self._lock:
            return self._resolve(pipeline_id)

    def _run(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline:
        with self._lock:
            pipeline = self._pipelines[pipeline_id]

            self._pipelines[pipeline_id] = replace(pipeline, status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.RUNNING)

            control = self._control[pipeline_id]
            control["pause_requested"] = False
            control["cancel_requested"] = False

            ordered_stages = tuple(sorted(pipeline.stages, key=lambda stage: stage.order))

            for index in range(self._progress[pipeline_id], len(ordered_stages)):
                stage = ordered_stages[index]
                executor = self._stage_executors.get(stage.type)

                if executor is None:
                    self._pipelines[pipeline_id] = replace(self._pipelines[pipeline_id], status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.FAILED)

                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                        f"Cannot execute pipeline ID {pipeline_id!r}: no executor is configured for stage "
                        f"type {stage.type!r}."
                    )

                try:
                    executor(pipeline.workspace_id, stage.configuration)
                except Exception as error:
                    self._pipelines[pipeline_id] = replace(self._pipelines[pipeline_id], status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.FAILED)

                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                        f"Pipeline ID {pipeline_id!r} failed at stage ID {stage.stage_id!r}: {error}"
                    ) from error

                self._progress[pipeline_id] = index + 1

                if self._event_bus is not None:
                    self._event_bus.publish(
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEvent(
                            event_id=str(uuid4()),
                            pipeline_id=pipeline_id,
                            stage_id=stage.stage_id,
                            event_type="stage_completed",
                            timestamp=datetime.now(timezone.utc),
                            payload={},
                        )
                    )

                if control["cancel_requested"]:
                    self._pipelines[pipeline_id] = replace(self._pipelines[pipeline_id], status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.CANCELLED)

                    return self._pipelines[pipeline_id]

                if control["pause_requested"]:
                    self._pipelines[pipeline_id] = replace(self._pipelines[pipeline_id], status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.PAUSED)

                    return self._pipelines[pipeline_id]

            self._pipelines[pipeline_id] = replace(self._pipelines[pipeline_id], status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus.COMPLETED)

            return self._pipelines[pipeline_id]

    def _resolve(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline:
        pipeline = self._pipelines.get(pipeline_id)

        if pipeline is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                f"No execution pipeline is registered under pipeline ID {pipeline_id!r}."
            )

        return pipeline

    def _validate_id(self, pipeline_id: str) -> None:
        if pipeline_id is None or not pipeline_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineError(
                "Cannot operate with an empty or blank pipeline ID."
            )
