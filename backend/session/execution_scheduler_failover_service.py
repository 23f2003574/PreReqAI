from threading import (
    RLock,
)

from uuid import uuid4

from .execution_scheduler_failover import (
    ExecutionSchedulerFailover,
    STATUS_ACTIVE,
    STATUS_FAILED,
)

from .execution_scheduler_failover_error import (
    ExecutionSchedulerFailoverError,
)


class ExecutionSchedulerFailoverService:
    """
    Recovers scheduling for a scope when its active scheduler becomes
    unavailable, by falling back through an ordered list of backups.

    Composes with an existing scheduler availability service
    (anything exposing `is_available(scheduler_id)`), used as the
    source of truth for whether a scheduler can currently be
    selected.

    Behavior:
    - register() records a scope's primary and backup schedulers, in
      priority order, and immediately performs an initial selection
    - execute() re-evaluates a scope's selection: if the currently
      selected scheduler is still available, it is preserved as-is;
      otherwise the primary, then each backup in order, is tried
      until an available one is found
    - A scope fails over to FAILED, with no selected_scheduler, only
      when every configured scheduler is unavailable
    - select() and status() simply read the scope's last-computed
      selection without re-evaluating availability

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, availability_service):
        self._availability_service = availability_service
        self._configs_by_scope = {}
        self._states_by_scope = {}
        self._lock = RLock()

    def register(self, scope_id: str, schedulers) -> ExecutionSchedulerFailover:
        """
        Record a scope's primary and backup schedulers and perform an
        initial selection.

        Args:
            scope_id: The scope to configure
            schedulers: An ordered, non-empty sequence of unique
                scheduler IDs; the first is the primary, the rest are
                backups tried in the given order

        Raises:
            ExecutionSchedulerFailoverError: If scope_id is None or
                blank, or schedulers is empty or contains a blank or
                duplicate entry
        """

        self._validate_text(scope_id, "scope ID")

        if schedulers is None:
            raise ExecutionSchedulerFailoverError("Cannot register a scope with a None schedulers sequence.")

        ordered = list(schedulers)

        if not ordered:
            raise ExecutionSchedulerFailoverError("Cannot register a scope with an empty schedulers sequence.")

        for scheduler_id in ordered:
            if not isinstance(scheduler_id, str) or not scheduler_id.strip():
                raise ExecutionSchedulerFailoverError("Cannot register a scope with a blank scheduler ID.")

        if len(set(ordered)) != len(ordered):
            raise ExecutionSchedulerFailoverError("Cannot register a scope with duplicate scheduler IDs.")

        with self._lock:
            existing = self._configs_by_scope.get(scope_id)
            failover_id = existing["failover_id"] if existing is not None else str(uuid4())

            self._configs_by_scope[scope_id] = {
                "failover_id": failover_id,
                "primary": ordered[0],
                "backups": tuple(ordered[1:]),
            }
            self._states_by_scope.pop(scope_id, None)

            return self._execute_locked(scope_id)

    def execute(self, scope_id: str) -> ExecutionSchedulerFailover:
        """
        Re-evaluate a scope's scheduler selection.

        Raises:
            ExecutionSchedulerFailoverError: If scope_id is None or
                blank, or no schedulers are registered for it
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            self._require_registered(scope_id)

            return self._execute_locked(scope_id)

    def select(self, scope_id: str):
        """
        The scheduler currently responsible for scope_id, or None if
        it has failed over completely.

        Raises:
            ExecutionSchedulerFailoverError: If scope_id is None or
                blank, or no schedulers are registered for it
        """

        return self._resolve(scope_id).selected_scheduler

    def status(self, scope_id: str) -> str:
        """
        The current status of scope_id's failover configuration.

        Raises:
            ExecutionSchedulerFailoverError: If scope_id is None or
                blank, or no schedulers are registered for it
        """

        return self._resolve(scope_id).status

    def _execute_locked(self, scope_id: str) -> ExecutionSchedulerFailover:
        config = self._configs_by_scope[scope_id]
        all_schedulers = (config["primary"],) + config["backups"]

        current_state = self._states_by_scope.get(scope_id)
        current_selected = current_state.selected_scheduler if current_state is not None else None

        if current_selected is not None and self._is_available(current_selected):
            selected = current_selected
        else:
            selected = next((candidate for candidate in all_schedulers if self._is_available(candidate)), None)

        state = ExecutionSchedulerFailover(
            failover_id=config["failover_id"],
            scope_id=scope_id,
            primary_scheduler=config["primary"],
            backup_schedulers=config["backups"],
            selected_scheduler=selected,
            status=STATUS_ACTIVE if selected is not None else STATUS_FAILED,
        )

        self._states_by_scope[scope_id] = state

        return state

    def _is_available(self, scheduler_id: str) -> bool:
        try:
            return bool(self._availability_service.is_available(scheduler_id))
        except Exception:
            return False

    def _require_registered(self, scope_id: str) -> None:
        if scope_id not in self._configs_by_scope:
            raise ExecutionSchedulerFailoverError(f"No schedulers are registered for scope ID {scope_id!r}.")

    def _resolve(self, scope_id: str) -> ExecutionSchedulerFailover:
        self._validate_text(scope_id, "scope ID")

        with self._lock:
            self._require_registered(scope_id)

            return self._states_by_scope[scope_id]

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSchedulerFailoverError(f"Cannot use an empty or blank {field_name}.")
