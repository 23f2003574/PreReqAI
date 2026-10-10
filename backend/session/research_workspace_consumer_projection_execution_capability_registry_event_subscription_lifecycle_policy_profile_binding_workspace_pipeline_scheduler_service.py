from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_scheduler_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_schedule_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineScheduleResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_schedule import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedule,
)

_STATUS_PENDING = "pending"
_STATUS_DISPATCHED = "dispatched"
_STATUS_CANCELLED = "cancelled"


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerService:
    """
    Decides when a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution pipeline is allowed to run, honoring a scheduled start
    time, an execution window, and dependencies on other schedules,
    without the execution engine itself knowing anything about
    scheduling.

    The service's responsibility is deciding readiness, not running a
    pipeline itself. It does NOT execute pipelines; whoever runs them
    (for example, by way of a pipeline execution queue service) is
    expected to call ready() and enqueue whatever it returns.

    Behavior:
    - A schedule is eligible starting at its start_at and remains
      eligible for execution_window seconds afterward; past that, it
      is never returned by ready() unless reschedule() is called
    - A schedule with dependencies is not eligible until every
      schedule it depends on has itself been dispatched by a prior
      ready() call
    - ready() returns each eligible schedule at most once, transitions
      it out of pending, and orders its results chronologically by
      start_at
    - A cancelled schedule is never returned by ready(), regardless of
      timing or dependencies

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._schedules = {}
        self._status = {}
        self._lock = RLock()

    def schedule(self, request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedule) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineScheduleResult:
        """
        Register a new schedule.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError:
                If request is None or not a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedule, its schedule
                ID is already registered, its start_at is not in the
                future, or its dependencies would introduce a
                circular dependency
        """

        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                "Cannot schedule a None pipeline schedule."
            )

        if not isinstance(request, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedule):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                "Cannot schedule a pipeline schedule: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedule."
            )

        with self._lock:
            if request.schedule_id in self._schedules:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                    f"Schedule ID {request.schedule_id!r} is already registered."
                )

            if request.start_at <= datetime.now(timezone.utc):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                    f"Cannot schedule pipeline ID {request.pipeline_id!r}: start_at "
                    f"{request.start_at.isoformat()} is not in the future."
                )

            if self._creates_cycle(request):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                    f"Cannot schedule schedule ID {request.schedule_id!r}: its dependencies introduce a "
                    "circular dependency."
                )

            self._schedules[request.schedule_id] = request
            self._status[request.schedule_id] = _STATUS_PENDING

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineScheduleResult(scheduled=True, next_execution=request.start_at)

    def cancel(self, schedule_id: str) -> None:
        """
        Cancel a schedule so it is never returned by ready() again.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError:
                If schedule_id is None or blank, or no schedule is
                registered under it
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            self._resolve(schedule_id)

            self._status[schedule_id] = _STATUS_CANCELLED

    def ready(self) -> tuple:
        """
        Select every schedule that is currently eligible to run, in
        chronological order by start_at, and mark each dispatched so
        it is not returned again.

        Returns:
            The eligible schedules, in chronological order
        """

        now = datetime.now(timezone.utc)

        with self._lock:
            candidates = []

            for schedule_id, schedule in self._schedules.items():
                if self._status[schedule_id] != _STATUS_PENDING:
                    continue

                window_end = schedule.start_at + timedelta(seconds=schedule.execution_window)

                if not (schedule.start_at <= now <= window_end):
                    continue

                if not all(self._status.get(dependency_id) == _STATUS_DISPATCHED for dependency_id in schedule.depends_on):
                    continue

                candidates.append(schedule)

            candidates.sort(key=lambda schedule: schedule.start_at)

            for schedule in candidates:
                self._status[schedule.schedule_id] = _STATUS_DISPATCHED

            return tuple(candidates)

    def reschedule(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineScheduleResult:
        """
        Make a schedule eligible for ready() again.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError:
                If schedule_id is None or blank, no schedule is
                registered under it, or the schedule has been
                cancelled
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            schedule = self._resolve(schedule_id)

            if self._status[schedule_id] == _STATUS_CANCELLED:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                    f"Cannot reschedule schedule ID {schedule_id!r}: schedule is cancelled."
                )

            self._status[schedule_id] = _STATUS_PENDING

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineScheduleResult(scheduled=True, next_execution=schedule.start_at)

    def pending(self) -> tuple:
        """
        List every schedule still awaiting dispatch, in the order
        they were registered.
        """

        with self._lock:
            return tuple(
                schedule
                for schedule_id, schedule in self._schedules.items()
                if self._status[schedule_id] == _STATUS_PENDING
            )

    def _creates_cycle(self, new_schedule: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedule) -> bool:
        graph = {schedule_id: schedule.depends_on for schedule_id, schedule in self._schedules.items()}
        graph[new_schedule.schedule_id] = new_schedule.depends_on

        visiting = set()
        visited = set()

        def _visit(node):
            if node in visiting:
                return True

            if node in visited or node not in graph:
                return False

            visiting.add(node)

            for dependency_id in graph[node]:
                if _visit(dependency_id):
                    return True

            visiting.discard(node)
            visited.add(node)

            return False

        return _visit(new_schedule.schedule_id)

    def _resolve(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedule:
        schedule = self._schedules.get(schedule_id)

        if schedule is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                f"No pipeline schedule is registered under schedule ID {schedule_id!r}."
            )

        return schedule

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineSchedulerError(
                f"Cannot operate with an empty or blank {label}."
            )
