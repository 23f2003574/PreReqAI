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

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_observability_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_diagnostic_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDiagnosticReport,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_execution_trace import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionTrace,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityService:
    """
    Traces consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    pipeline stage executions and generates diagnostics from them,
    entirely independent of the pipeline's own execution flow.

    The service's responsibility is trace bookkeeping and diagnostic
    aggregation, not running a pipeline itself. It does NOT execute
    stages or pipelines, and it never affects whether or how a stage
    runs; whoever runs a stage (for example, a stage executor bound
    into a consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    pipeline service) is expected to call begin_trace() before the
    stage's own work and finish_trace() after, regardless of outcome.

    Behavior:
    - A (pipeline_id, stage_id) pair may have at most one running
      trace at a time; a prior trace for the same pair must finish
      before a new one can begin
    - A trace's duration is only counted once it has finished
    - report() sums the finished durations of a pipeline's traces,
      names the first stage whose trace failed, if any, and warns
      about any trace that never finished
    - purge() only removes finished traces; a currently running trace
      is never purged, regardless of how old it is

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._traces = {}
        self._active_trace_id_by_stage = {}
        self._lock = RLock()

    def begin_trace(self, pipeline_id: str, stage_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionTrace:
        """
        Start tracing a stage's execution.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError:
                If pipeline_id or stage_id is None or blank, or the
                pair already has an active trace
        """

        self._validate_id(pipeline_id, "pipeline ID")
        self._validate_id(stage_id, "stage ID")

        key = (pipeline_id, stage_id)

        with self._lock:
            if key in self._active_trace_id_by_stage:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                    f"Cannot begin a trace for pipeline ID {pipeline_id!r} stage ID {stage_id!r}: an "
                    "active trace already exists."
                )

            trace = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionTrace(
                trace_id=str(uuid4()),
                pipeline_id=pipeline_id,
                stage_id=stage_id,
                started_at=datetime.now(timezone.utc),
                finished_at=None,
                status="running",
            )

            self._traces[trace.trace_id] = trace
            self._active_trace_id_by_stage[key] = trace.trace_id

            return trace

    def finish_trace(self, trace_id: str, successful: bool = True) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionTrace:
        """
        Finish a running trace.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError:
                If trace_id is None or blank, no trace is registered
                under it, or the trace has already finished
        """

        self._validate_id(trace_id, "trace ID")

        with self._lock:
            trace = self._traces.get(trace_id)

            if trace is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                    f"No pipeline execution trace is registered under trace ID {trace_id!r}."
                )

            if trace.status != "running":
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                    f"Cannot finish trace ID {trace_id!r}: trace has already finished."
                )

            finished = replace(
                trace,
                finished_at=datetime.now(timezone.utc),
                status="succeeded" if successful else "failed",
            )

            self._traces[trace_id] = finished
            del self._active_trace_id_by_stage[(trace.pipeline_id, trace.stage_id)]

            return finished

    def report(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDiagnosticReport:
        """
        Generate a diagnostic report from a pipeline's traces.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError:
                If pipeline_id is None or blank, or no trace has ever
                been recorded for it
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            traces = [trace for trace in self._traces.values() if trace.pipeline_id == pipeline_id]

            if not traces:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                    f"No pipeline execution traces are recorded for pipeline ID {pipeline_id!r}."
                )

            duration = sum(
                (trace.finished_at - trace.started_at).total_seconds()
                for trace in traces
                if trace.finished_at is not None
            )

            failed_stage = next((trace.stage_id for trace in traces if trace.status == "failed"), None)

            warnings = tuple(
                f"Stage ID {trace.stage_id!r} has not finished."
                for trace in traces
                if trace.status == "running"
            )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDiagnosticReport(
                pipeline_id=pipeline_id,
                duration=duration,
                failed_stage=failed_stage,
                warnings=warnings,
            )

    def active_traces(self) -> tuple:
        """
        List every currently running trace.
        """

        with self._lock:
            return tuple(trace for trace in self._traces.values() if trace.status == "running")

    def purge(self, before_timestamp: datetime) -> int:
        """
        Remove every finished trace started before a given time.

        Args:
            before_timestamp: Finished traces started strictly
                earlier than this are removed; a running trace is
                never removed, regardless of when it started

        Returns:
            The number of traces removed

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError:
                If before_timestamp is None
        """

        if before_timestamp is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                "Cannot purge with a None timestamp."
            )

        with self._lock:
            to_remove = [
                trace_id
                for trace_id, trace in self._traces.items()
                if trace.status != "running" and trace.started_at < before_timestamp
            ]

            for trace_id in to_remove:
                del self._traces[trace_id]

            return len(to_remove)

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineObservabilityError(
                f"Cannot operate with an empty or blank {label}."
            )
