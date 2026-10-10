from threading import (
    RLock,
)

from typing import Mapping

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_resource_budget import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_quota_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_quota_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaService:
    """
    Enforces a shared pool of runtime, memory, and parallel-task
    capacity across consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution pipelines, so no single pipeline can reserve
    more than what remains and starve the others.

    The service's responsibility is quota bookkeeping, not running a
    pipeline itself. It does NOT execute pipelines; whoever runs one
    (for example, by way of a pipeline execution scheduler or queue
    service) is expected to call reserve() before it starts and
    release() once it completes or is cancelled.

    Behavior:
    - A pipeline must have a registered budget before it can be
      reserved, validated, or its usage inspected
    - reserve() atomically checks the registered budget against the
      remaining pool and, if it fits, deducts it; if not, the pool is
      left untouched and the rejection is reported through the
      returned result rather than raised, since exceeding the quota
      is an expected outcome, not a validation failure
    - release() returns a pipeline's reserved amounts to the pool

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, max_runtime: float, max_memory: float, max_parallel_tasks: int):
        """
        Args:
            max_runtime: The quota pool's total runtime capacity, in
                seconds
            max_memory: The quota pool's total memory capacity, in
                megabytes
            max_parallel_tasks: The quota pool's total parallel task
                capacity

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError:
                If any capacity is not a non-negative number, or
                max_parallel_tasks is not a non-negative integer
        """

        if (
            max_runtime is None
            or isinstance(max_runtime, bool)
            or not isinstance(max_runtime, (int, float))
            or max_runtime < 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot initialize a pipeline quota service with a max_runtime that is not a non-negative "
                "number."
            )

        if (
            max_memory is None
            or isinstance(max_memory, bool)
            or not isinstance(max_memory, (int, float))
            or max_memory < 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot initialize a pipeline quota service with a max_memory that is not a non-negative "
                "number."
            )

        if (
            max_parallel_tasks is None
            or isinstance(max_parallel_tasks, bool)
            or not isinstance(max_parallel_tasks, int)
            or max_parallel_tasks < 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot initialize a pipeline quota service with a max_parallel_tasks that is not a "
                "non-negative integer."
            )

        self._remaining_runtime = max_runtime
        self._remaining_memory = max_memory
        self._remaining_parallel_tasks = max_parallel_tasks
        self._budgets_by_id = {}
        self._budgets_by_pipeline = {}
        self._reservations = {}
        self._lock = RLock()

    def register(self, budget: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget:
        """
        Register a pipeline's resource budget.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError:
                If budget is None or not a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget, its budget ID is
                already registered, or its pipeline already has a
                registered budget
        """

        if budget is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot register a None pipeline resource budget."
            )

        if not isinstance(budget, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                "Cannot register a pipeline resource budget: budget must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget."
            )

        with self._lock:
            if budget.budget_id in self._budgets_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                    f"Budget ID {budget.budget_id!r} is already registered."
                )

            if budget.pipeline_id in self._budgets_by_pipeline:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                    f"Pipeline ID {budget.pipeline_id!r} already has a registered resource budget."
                )

            self._budgets_by_id[budget.budget_id] = budget
            self._budgets_by_pipeline[budget.pipeline_id] = budget

            return budget

    def reserve(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaResult:
        """
        Reserve a pipeline's registered budget from the remaining
        quota pool.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError:
                If pipeline_id is None or blank, no budget is
                registered for it, or a reservation is already active
                for it
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            if pipeline_id in self._reservations:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                    f"Cannot reserve budget for pipeline ID {pipeline_id!r}: a reservation is already active."
                )

            budget = self._resolve_budget(pipeline_id)

            fits, reason = self._fits_within_remaining(budget)

            if not fits:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaResult(accepted=False, reason=reason, remaining_budget=self._remaining_snapshot())

            self._remaining_runtime -= budget.max_runtime
            self._remaining_memory -= budget.max_memory
            self._remaining_parallel_tasks -= budget.max_parallel_tasks

            self._reservations[pipeline_id] = budget

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaResult(
                accepted=True,
                reason="Budget reserved.",
                remaining_budget=self._remaining_snapshot(),
            )

    def release(self, pipeline_id: str) -> None:
        """
        Return a pipeline's reserved budget to the quota pool.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError:
                If pipeline_id is None or blank, or no reservation is
                active for it
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            budget = self._reservations.pop(pipeline_id, None)

            if budget is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                    f"No active budget reservation for pipeline ID {pipeline_id!r}."
                )

            self._remaining_runtime += budget.max_runtime
            self._remaining_memory += budget.max_memory
            self._remaining_parallel_tasks += budget.max_parallel_tasks

    def validate(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaResult:
        """
        Check whether a pipeline's registered budget currently fits
        within the remaining quota pool, without reserving it.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError:
                If pipeline_id is None or blank, or no budget is
                registered for it
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            budget = self._resolve_budget(pipeline_id)

            fits, reason = self._fits_within_remaining(budget)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaResult(accepted=fits, reason=reason, remaining_budget=self._remaining_snapshot())

    def remaining(self) -> Mapping:
        """
        Report the quota pool's current remaining capacity.
        """

        with self._lock:
            return self._remaining_snapshot()

    def usage(self, pipeline_id: str):
        """
        Look up what a pipeline currently has reserved.

        Returns:
            The pipeline's reserved budget, or None if it has no
            active reservation

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError:
                If pipeline_id is None or blank
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            return self._reservations.get(pipeline_id)

    def _fits_within_remaining(self, budget: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget):
        if budget.max_runtime > self._remaining_runtime:
            return False, (
                f"Requested max_runtime {budget.max_runtime!r} exceeds remaining runtime budget "
                f"{self._remaining_runtime!r}."
            )

        if budget.max_memory > self._remaining_memory:
            return False, (
                f"Requested max_memory {budget.max_memory!r} exceeds remaining memory budget "
                f"{self._remaining_memory!r}."
            )

        if budget.max_parallel_tasks > self._remaining_parallel_tasks:
            return False, (
                f"Requested max_parallel_tasks {budget.max_parallel_tasks!r} exceeds remaining parallel "
                f"task budget {self._remaining_parallel_tasks!r}."
            )

        return True, "Budget fits within the remaining quota."

    def _remaining_snapshot(self) -> Mapping:
        return MappingProxyType(
            {
                "max_runtime": self._remaining_runtime,
                "max_memory": self._remaining_memory,
                "max_parallel_tasks": self._remaining_parallel_tasks,
            }
        )

    def _resolve_budget(self, pipeline_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineResourceBudget:
        budget = self._budgets_by_pipeline.get(pipeline_id)

        if budget is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                f"No resource budget is registered for pipeline ID {pipeline_id!r}."
            )

        return budget

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQuotaError(
                f"Cannot operate with an empty or blank {label}."
            )
