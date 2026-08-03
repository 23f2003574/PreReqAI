from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_dashboard_entry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardEntry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_dashboard_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_dashboard_summary import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardSummary,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardService:
    """
    Exposes a read-only, aggregated view of consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace execution pipelines, so a
    monitoring client can see what is active, queued, completed, or
    failed without depending on the execution, queue, or
    observability services' own internals.

    The service's responsibility is aggregation and presentation, not
    execution. It adds no execution logic of its own: every field it
    reports is derived from the existing execution, queue, and
    observability services' already-public query methods.

    Behavior and known limitations, both a direct consequence of only
    ever calling the reused services' existing read-only methods:
    - summary() is built entirely from the queue service's own
      statistics()
    - active() lists every pipeline with a currently running trace,
      derived from the observability service's active_traces(), the
      only genuinely enumerable source available
    - queue() reflects only the queue service's peek(): the single
      next-eligible item, since the queue service exposes no way to
      list every queued item without dequeuing it
    - history() is built from pipelines this service has itself
      observed reaching a finished state through pipeline() calls,
      newest observation first, since none of the reused services
      expose a way to enumerate finished pipelines directly

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_pipeline_service, queue_service, observability_service):
        """
        Args:
            execution_pipeline_service: The service used to resolve a
                pipeline's current status. Any object exposing
                `status(pipeline_id)`, returning an object with a
                `status` attribute whose value has a `.value`
                attribute, is accepted
            queue_service: The service used to resolve queue counts
                and the next eligible item. Any object exposing
                `statistics()` (returning an object with `queued`,
                `running`, `completed`, and `failed` attributes) and
                `peek()` (returning an object with a `pipeline_id`
                attribute, or None) is accepted
            observability_service: The service used to resolve
                currently running stages. Any object exposing
                `active_traces()`, returning objects with
                `pipeline_id`, `stage_id`, and `started_at`
                attributes, is accepted
        """

        self._execution_pipeline_service = execution_pipeline_service
        self._queue_service = queue_service
        self._observability_service = observability_service
        self._history = []
        self._recorded_pipeline_ids = set()
        self._lock = RLock()

    def summary(self) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardSummary:
        """
        Aggregate pipeline counts by state from the queue service.
        """

        with self._lock:
            stats = self._queue_service.statistics()

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardSummary(
                active=stats.running,
                queued=stats.queued,
                completed=stats.completed,
                failed=stats.failed,
            )

    def active(self) -> tuple:
        """
        List every pipeline with a currently running stage.
        """

        with self._lock:
            entries = []
            seen_pipeline_ids = set()

            for trace in self._observability_service.active_traces():
                if trace.pipeline_id in seen_pipeline_ids:
                    continue

                seen_pipeline_ids.add(trace.pipeline_id)

                status_value = self._resolve_status_value(trace.pipeline_id, default="running")

                entries.append(
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardEntry(
                        pipeline_id=trace.pipeline_id,
                        status=status_value,
                        current_stage=trace.stage_id,
                        progress=0.0,
                        started_at=trace.started_at,
                    )
                )

            return tuple(entries)

    def queue(self) -> tuple:
        """
        List the next eligible queued pipeline, if any.
        """

        with self._lock:
            next_item = self._queue_service.peek()

            if next_item is None:
                return ()

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardEntry(
                    pipeline_id=next_item.pipeline_id,
                    status="queued",
                    current_stage=None,
                    progress=0.0,
                    started_at=None,
                ),
            )

    def history(self, limit: int) -> tuple:
        """
        List pipelines this service has observed finishing, most
        recently observed first.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError:
                If limit is not a positive integer
        """

        if limit is None or isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError(
                f"Invalid pipeline dashboard history limit {limit!r}; limit must be a positive integer."
            )

        with self._lock:
            ordered = sorted(self._history, key=lambda observed: observed[0], reverse=True)

            return tuple(entry for _, entry in ordered[:limit])

    def pipeline(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardEntry:
        """
        Look up a single pipeline's current dashboard entry.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError:
                If pipeline_id is None or blank, or the execution
                pipeline service does not recognize it
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            status_value = self._resolve_status_value(pipeline_id, default=None)

            if status_value is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError(
                    f"No pipeline is known under pipeline ID {pipeline_id!r}."
                )

            running_trace = next(
                (
                    trace
                    for trace in self._observability_service.active_traces()
                    if trace.pipeline_id == pipeline_id
                ),
                None,
            )

            entry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardEntry(
                pipeline_id=pipeline_id,
                status=status_value,
                current_stage=running_trace.stage_id if running_trace is not None else None,
                progress=1.0 if status_value == "completed" else 0.0,
                started_at=running_trace.started_at if running_trace is not None else None,
            )

            if status_value in ("completed", "failed") and pipeline_id not in self._recorded_pipeline_ids:
                self._recorded_pipeline_ids.add(pipeline_id)
                self._history.append((datetime.now(timezone.utc), entry))

            return entry

    def _resolve_status_value(self, pipeline_id: str, default):
        try:
            resolved = self._execution_pipeline_service.status(pipeline_id)
        except Exception:
            return default

        return resolved.status.value

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineDashboardError(
                f"Cannot operate with an empty or blank {label}."
            )
