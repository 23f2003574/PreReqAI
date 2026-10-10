from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_dependency_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_dependency import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependency,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_dependency_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionDependencyResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyService:
    """
    Gates consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace session
    schedules behind their prerequisite execution sessions, so a
    schedule is only ever eligible for execution once every session
    it depends on has completed successfully.

    The service's responsibility is dependency bookkeeping and
    completion checking, not execution itself. It does NOT select or
    trigger a schedule for execution; it relies on the existing
    execution session service, given at construction time, only to
    confirm a prerequisite session ID is genuinely known and to read
    its current status. A session's FINISHED status is treated as
    having completed successfully; ACTIVE and CANCELLED are both
    treated as not yet satisfying a dependency, since the execution
    session service does not persist a session's success/failure
    beyond its lifecycle status. A caller, such as the session
    scheduler, is expected to call validate() before selecting a
    schedule for execution.

    Behavior:
    - A schedule may have any number of dependencies; all of them
      must complete before the schedule is satisfied
    - add() rejects a dependency that would form a cycle, walking the
      dependency graph from the new prerequisite back to the schedule
      it would be added to, treating any prerequisite session ID that
      is itself a dependent schedule ID as a further hop
    - remove() drops a single dependency immediately; the schedule it
      belonged to is re-evaluated on its next validate() call
    - blocked() and ready() are computed fresh from current session
      state on every call: a schedule is unblocked automatically, the
      moment its remaining prerequisites finish, without any explicit
      unblocking step
    - A schedule's dependencies are kept in the order they were
      added; blocking_sessions in a validate() result follows that
      same order

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service):
        """
        Args:
            execution_session_service: The service used to confirm a
                prerequisite session ID is known, and to read its
                current status. Any object exposing `session(session_id)`,
                raising if the session is unknown and otherwise
                returning an object with a `status` attribute, is
                accepted
        """

        self._execution_session_service = execution_session_service
        self._dependencies = {}
        self._dependency_ids_by_schedule_id = {}
        self._lock = RLock()

    def add(
        self,
        schedule_id: str,
        prerequisite: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependency,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependency:
        """
        Add a dependency on behalf of a schedule.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError:
                If schedule_id is None or blank, prerequisite is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependency
                belonging to schedule_id, the execution session
                service does not recognize the prerequisite's session
                ID, the dependency ID is already registered, or adding
                it would form a dependency cycle
        """

        self._validate_id(schedule_id, "schedule ID")

        if not isinstance(prerequisite, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependency):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                "Cannot add an invalid dependency: prerequisite must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependency."
            )

        if prerequisite.schedule_id != schedule_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                f"Cannot add a dependency for schedule ID {prerequisite.schedule_id!r} on behalf of schedule ID "
                f"{schedule_id!r}."
            )

        with self._lock:
            self._ensure_session_known(prerequisite.prerequisite_session_id)

            if prerequisite.dependency_id in self._dependencies:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                    f"Dependency ID {prerequisite.dependency_id!r} is already registered."
                )

            if self._would_cycle(schedule_id, prerequisite.prerequisite_session_id):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                    f"Cannot add a dependency from schedule ID {schedule_id!r} on prerequisite session ID "
                    f"{prerequisite.prerequisite_session_id!r}: it would form a dependency cycle."
                )

            self._dependencies[prerequisite.dependency_id] = prerequisite
            self._dependency_ids_by_schedule_id.setdefault(schedule_id, []).append(prerequisite.dependency_id)

            return prerequisite

    def remove(self, dependency_id: str) -> None:
        """
        Remove a dependency immediately.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError:
                If dependency_id is None or blank, or no dependency is
                registered under it
        """

        self._validate_id(dependency_id, "dependency ID")

        with self._lock:
            dependency = self._resolve(dependency_id)

            del self._dependencies[dependency_id]

            schedule_dependency_ids = self._dependency_ids_by_schedule_id.get(dependency.schedule_id)

            if schedule_dependency_ids is not None and dependency_id in schedule_dependency_ids:
                schedule_dependency_ids.remove(dependency_id)

                if not schedule_dependency_ids:
                    del self._dependency_ids_by_schedule_id[dependency.schedule_id]

    def validate(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionDependencyResult:
        """
        Check whether every prerequisite session a schedule depends on
        has completed successfully.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            blocking = tuple(
                dependency.prerequisite_session_id
                for dependency in self._ordered_dependencies(schedule_id)
                if not self._is_complete(dependency.prerequisite_session_id)
            )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionDependencyResult(
                satisfied=not blocking,
                blocking_sessions=blocking,
            )

    def blocked(self) -> tuple:
        """
        List every schedule ID with at least one unfinished
        prerequisite, in the order dependencies were first added for
        it.
        """

        with self._lock:
            return tuple(
                schedule_id
                for schedule_id in self._dependency_ids_by_schedule_id
                if any(
                    not self._is_complete(dependency.prerequisite_session_id)
                    for dependency in self._ordered_dependencies(schedule_id)
                )
            )

    def ready(self) -> tuple:
        """
        List every schedule ID whose dependencies, if any, have all
        completed successfully, in the order dependencies were first
        added for it.
        """

        with self._lock:
            return tuple(
                schedule_id
                for schedule_id in self._dependency_ids_by_schedule_id
                if all(
                    self._is_complete(dependency.prerequisite_session_id)
                    for dependency in self._ordered_dependencies(schedule_id)
                )
            )

    def _ordered_dependencies(self, schedule_id: str) -> tuple:
        return tuple(
            self._dependencies[dependency_id]
            for dependency_id in self._dependency_ids_by_schedule_id.get(schedule_id, ())
        )

    def _would_cycle(self, schedule_id: str, prerequisite_session_id: str) -> bool:
        visited = set()
        stack = [prerequisite_session_id]

        while stack:
            node = stack.pop()

            if node == schedule_id:
                return True

            if node in visited:
                continue

            visited.add(node)

            for dependency in self._ordered_dependencies(node):
                stack.append(dependency.prerequisite_session_id)

        return False

    def _is_complete(self, session_id: str) -> bool:
        session = self._execution_session_service.session(session_id)

        return session.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.FINISHED

    def _ensure_session_known(self, session_id: str) -> None:
        try:
            self._execution_session_service.session(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                f"No execution session is known under session ID {session_id!r}."
            ) from error

    def _resolve(self, dependency_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependency:
        dependency = self._dependencies.get(dependency_id)

        if dependency is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                f"No session schedule dependency is registered under dependency ID {dependency_id!r}."
            )

        return dependency

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleDependencyError(
                f"Cannot operate with an empty or blank {label}."
            )
