from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from numbers import (
    Real,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_runtime_state import (
    TERMINAL_STATES,
)

from .execution_runtime_resource import (
    ExecutionRuntimeResource,
    STATUS_ALLOCATED,
    STATUS_RELEASED,
)

from .execution_runtime_resource_error import (
    ExecutionRuntimeResourceError,
)

ACTIVE_STATES = ("RUNNING", "PAUSED")


class ExecutionRuntimeResourceService:
    """
    Tracks and guarantees release of resources owned by a runtime
    when it stops, fails, or is cancelled.

    Composes with an existing runtime state service (anything
    exposing `state(runtime_id) -> object with .state`, matching
    ExecutionRuntimeStateService), used to confirm a runtime is
    currently active before it can allocate resources, and to detect
    runtimes that reached a terminal state while still holding
    resources.

    Behavior:
    - allocate() admits a new ALLOCATED claim, but only for a runtime
      whose current state is RUNNING or PAUSED, and only with a
      positive amount
    - release() is idempotent: releasing an already-released claim
      simply returns it unchanged
    - release_all() releases every currently-ALLOCATED claim held by
      a runtime
    - active() reports a runtime's currently-ALLOCATED claims
    - leaked() reports every currently-ALLOCATED claim whose runtime
      has since reached a terminal state (STOPPED, FAILED), violating
      the rule that terminal runtimes must hold no active resources

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, state_service):
        self._state_service = state_service
        self._resources_by_id = {}
        self._lock = RLock()

    def allocate(self, runtime_id: str, resource_type: str, amount: float) -> ExecutionRuntimeResource:
        """
        Claim amount of resource_type on behalf of runtime_id.

        Raises:
            ExecutionRuntimeResourceError: If runtime_id or
                resource_type is None or blank, amount is not a
                positive number, runtime_id is unknown, or its
                current state is not RUNNING or PAUSED
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(resource_type, "resource type")
        self._validate_amount(amount)

        current_state = self._current_state(runtime_id)

        if current_state not in ACTIVE_STATES:
            raise ExecutionRuntimeResourceError(
                f"Cannot allocate resources for runtime ID {runtime_id!r}: "
                f"it is not active (state is {current_state!r})."
            )

        with self._lock:
            resource = ExecutionRuntimeResource(
                resource_id=str(uuid4()),
                runtime_id=runtime_id,
                resource_type=resource_type,
                amount=amount,
                status=STATUS_ALLOCATED,
                released_at=None,
            )

            self._resources_by_id[resource.resource_id] = resource

            return resource

    def release(self, resource_id: str) -> ExecutionRuntimeResource:
        """
        Release a resource claim. Idempotent: releasing an
        already-released claim simply returns it unchanged.

        Raises:
            ExecutionRuntimeResourceError: If resource_id is None or
                blank, or no resource claim is registered under it
        """

        self._validate_text(resource_id, "resource ID")

        with self._lock:
            resource = self._resolve(resource_id)

            if resource.status == STATUS_RELEASED:
                return resource

            released = replace(
                resource,
                status=STATUS_RELEASED,
                released_at=datetime.now(timezone.utc),
            )
            self._resources_by_id[resource_id] = released

            return released

    def release_all(self, runtime_id: str) -> tuple:
        """
        Release every currently-ALLOCATED resource claim held by
        runtime_id.

        Raises:
            ExecutionRuntimeResourceError: If runtime_id is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            released = []

            for resource_id, resource in list(self._resources_by_id.items()):
                if resource.runtime_id == runtime_id and resource.status == STATUS_ALLOCATED:
                    released.append(self.release(resource_id))

            return tuple(released)

    def active(self, runtime_id: str) -> tuple:
        """
        The currently-ALLOCATED resource claims held by runtime_id.
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            return tuple(
                resource
                for resource in self._resources_by_id.values()
                if resource.runtime_id == runtime_id and resource.status == STATUS_ALLOCATED
            )

    def leaked(self) -> tuple:
        """
        Every currently-ALLOCATED resource claim whose runtime has
        reached a terminal state (STOPPED, FAILED) without releasing
        it.
        """

        with self._lock:
            result = []

            for resource in self._resources_by_id.values():
                if resource.status != STATUS_ALLOCATED:
                    continue

                try:
                    current_state = self._current_state(resource.runtime_id)
                except ExecutionRuntimeResourceError:
                    continue

                if current_state in TERMINAL_STATES:
                    result.append(resource)

            return tuple(result)

    def _current_state(self, runtime_id: str) -> str:
        try:
            return self._state_service.state(runtime_id).state
        except Exception as error:
            raise ExecutionRuntimeResourceError(
                f"Cannot resolve runtime ID {runtime_id!r}: it is unknown."
            ) from error

    def _resolve(self, resource_id: str) -> ExecutionRuntimeResource:
        resource = self._resources_by_id.get(resource_id)

        if resource is None:
            raise ExecutionRuntimeResourceError(
                f"No resource claim is recorded under resource ID {resource_id!r}."
            )

        return resource

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeResourceError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_amount(amount) -> None:
        if amount is None or isinstance(amount, bool) or not isinstance(amount, Real) or amount <= 0:
            raise ExecutionRuntimeResourceError(f"Cannot use a non-positive amount: {amount!r}.")
