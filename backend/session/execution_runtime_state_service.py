from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_runtime_state import (
    ExecutionRuntimeState,
    STATE_STARTING,
    STATES,
    TERMINAL_STATES,
)

from .execution_runtime_state_error import (
    ExecutionRuntimeStateError,
)

TRANSITIONS = {
    STATE_STARTING: ("RUNNING", "FAILED"),
    "RUNNING": ("PAUSED", "STOPPING", "FAILED"),
    "PAUSED": ("RUNNING", "STOPPING", "FAILED"),
    "STOPPING": ("STOPPED", "FAILED"),
    "STOPPED": (),
    "FAILED": (),
}


class ExecutionRuntimeStateService:
    """
    Tracks the authoritative lifecycle state of a running execution.

    A runtime with no recorded state yet can only transition into
    STARTING; every subsequent transition is validated against
    TRANSITIONS for the runtime's current state.

    Behavior:
    - transition() admits a new state record, but only if the move
      from the runtime's current state to the target is a valid
      transition; every record is appended to that runtime's history
      rather than replacing the prior one
    - Terminal states (STOPPED, FAILED) never transition; every
      target is rejected once a runtime reaches one
    - state() reports a runtime's current (most recent) state
    - history() reports every state a runtime has passed through, in
      the order it passed through them
    - can_transition() reports whether a move to target is currently
      valid for runtime_id, without performing it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._history_by_runtime = {}
        self._lock = RLock()

    def transition(self, runtime_id: str, state: str, reason: str) -> ExecutionRuntimeState:
        """
        Move runtime_id to state, recording reason and appending the
        result to its history.

        Raises:
            ExecutionRuntimeStateError: If runtime_id, state, or
                reason is None or blank, state is not a known state,
                or the move from the runtime's current state to state
                is not a valid transition
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(reason, "reason")
        self._validate_state(state)

        with self._lock:
            if not self._can_transition_locked(runtime_id, state):
                current = self._current_locked(runtime_id)
                current_label = current.state if current is not None else "no recorded state"
                raise ExecutionRuntimeStateError(
                    f"Cannot transition runtime ID {runtime_id!r} from {current_label!r} to {state!r}."
                )

            record = ExecutionRuntimeState(
                runtime_id=runtime_id,
                state=state,
                reason=reason,
                updated_at=datetime.now(timezone.utc),
            )

            self._history_by_runtime.setdefault(runtime_id, []).append(record)

            return record

    def state(self, runtime_id: str) -> ExecutionRuntimeState:
        """
        The current (most recent) state of runtime_id.

        Raises:
            ExecutionRuntimeStateError: If runtime_id is None or
                blank, or no state has been recorded for it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            current = self._current_locked(runtime_id)

            if current is None:
                raise ExecutionRuntimeStateError(
                    f"No state is recorded for runtime ID {runtime_id!r}."
                )

            return current

    def history(self, runtime_id: str) -> tuple:
        """
        Every state runtime_id has passed through, oldest first.

        Raises:
            ExecutionRuntimeStateError: If runtime_id is None or
                blank, or no state has been recorded for it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            records = self._history_by_runtime.get(runtime_id)

            if not records:
                raise ExecutionRuntimeStateError(
                    f"No state is recorded for runtime ID {runtime_id!r}."
                )

            return tuple(records)

    def can_transition(self, runtime_id: str, target: str) -> bool:
        """
        Whether a move to target is currently valid for runtime_id.
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_state(target)

        with self._lock:
            return self._can_transition_locked(runtime_id, target)

    def _can_transition_locked(self, runtime_id: str, target: str) -> bool:
        current = self._current_locked(runtime_id)

        if current is None:
            return target == STATE_STARTING

        if current.state in TERMINAL_STATES:
            return False

        return target in TRANSITIONS[current.state]

    def _current_locked(self, runtime_id: str):
        records = self._history_by_runtime.get(runtime_id)

        if not records:
            return None

        return records[-1]

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeStateError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_state(state: str) -> None:
        if state not in STATES:
            raise ExecutionRuntimeStateError(f"Unknown state: {state!r}.")
