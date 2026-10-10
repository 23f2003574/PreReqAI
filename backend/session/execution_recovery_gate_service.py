from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_recovery_gate_error import (
    ExecutionRecoveryGateError,
)

from .execution_recovery_gate import (
    ExecutionRecoveryGate,
)


class ExecutionRecoveryGateService:
    """
    Blocks recovery until a session's checkpoint passes every
    required pre-resume check.

    Checkpoints, their validation outcome, and a session's
    unresolved conflicts are assumed to already exist elsewhere;
    this service depends on plain resolver callables for them rather
    than a concrete store:
    - checkpoint_resolver(checkpoint_id) -> checkpoint or None
    - checkpoint_validation_resolver(checkpoint_id) -> True if the
      checkpoint has passed validation, False or None otherwise
    - conflicts_resolver(session_id) -> the session's outstanding,
      unresolved conflicts

    Behavior:
    - create() registers a new PENDING gate for a session's
      checkpoint, with no checks run yet
    - evaluate() runs the validation, conflict, and checkpoint
      checks and records the outcome; it may be called again at any
      time to re-evaluate after state changes, and always reflects
      the current state rather than any earlier evaluation
    - failed() lists the checks that failed as of the last
      evaluation, each retaining its reason
    - open() reports whether the gate is currently OPEN, meaning
      recovery is allowed

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, checkpoint_resolver, checkpoint_validation_resolver, conflicts_resolver):
        self._checkpoint_resolver = checkpoint_resolver
        self._checkpoint_validation_resolver = checkpoint_validation_resolver
        self._conflicts_resolver = conflicts_resolver
        self._gates_by_id = {}
        self._lock = RLock()

    def create(self, session_id: str, checkpoint_id: str) -> ExecutionRecoveryGate:
        """
        Register a new PENDING gate for a session's checkpoint, with
        no checks run yet.

        Raises:
            ExecutionRecoveryGateError: If session_id or
                checkpoint_id is None or blank
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(checkpoint_id, "checkpoint ID")

        with self._lock:
            gate = ExecutionRecoveryGate(session_id=session_id, checkpoint_id=checkpoint_id)

            self._gates_by_id[gate.gate_id] = gate

            return gate

    def evaluate(self, gate_id: str) -> ExecutionRecoveryGate:
        """
        Run the validation, conflict, and checkpoint checks against
        current state and record the outcome. Safe to call again at
        any time; each call reflects current state, not any earlier
        evaluation.

        Raises:
            ExecutionRecoveryGateError: If gate_id is None or blank,
                or no gate is known under it
        """

        self._validate_id(gate_id, "gate ID")

        with self._lock:
            gate = self._resolve(gate_id)

            checks = (
                self._validation_check(gate.checkpoint_id),
                self._conflict_check(gate.session_id),
                self._checkpoint_check(gate.checkpoint_id),
            )

            status = "OPEN" if all(check["passed"] for check in checks) else "BLOCKED"

            updated = replace(gate, checks=checks, status=status)
            self._gates_by_id[gate_id] = updated

            return updated

    def failed(self, gate_id: str) -> tuple:
        """
        List the checks that failed as of the last evaluation.

        Raises:
            ExecutionRecoveryGateError: If gate_id is None or blank,
                or no gate is known under it
        """

        self._validate_id(gate_id, "gate ID")

        with self._lock:
            return tuple(check for check in self._resolve(gate_id).checks if not check["passed"])

    def open(self, gate_id: str) -> bool:
        """
        Report whether the gate is currently OPEN, meaning recovery
        is allowed.

        Raises:
            ExecutionRecoveryGateError: If gate_id is None or blank,
                or no gate is known under it
        """

        self._validate_id(gate_id, "gate ID")

        with self._lock:
            return self._resolve(gate_id).status == "OPEN"

    def _checkpoint_check(self, checkpoint_id: str) -> dict:
        if self._checkpoint_resolver(checkpoint_id) is not None:
            return {"name": "checkpoint", "passed": True, "reason": None}

        return {
            "name": "checkpoint",
            "passed": False,
            "reason": f"No checkpoint is known under checkpoint ID {checkpoint_id!r}.",
        }

    def _validation_check(self, checkpoint_id: str) -> dict:
        if self._checkpoint_validation_resolver(checkpoint_id):
            return {"name": "validation", "passed": True, "reason": None}

        return {
            "name": "validation",
            "passed": False,
            "reason": f"Checkpoint ID {checkpoint_id!r} has not passed validation.",
        }

    def _conflict_check(self, session_id: str) -> dict:
        unresolved_conflicts = tuple(self._conflicts_resolver(session_id) or ())

        if not unresolved_conflicts:
            return {"name": "conflict", "passed": True, "reason": None}

        return {
            "name": "conflict",
            "passed": False,
            "reason": f"{len(unresolved_conflicts)} unresolved conflict(s) remain for session ID {session_id!r}.",
        }

    def _resolve(self, gate_id: str) -> ExecutionRecoveryGate:
        gate = self._gates_by_id.get(gate_id)

        if gate is None:
            raise ExecutionRecoveryGateError(f"No gate is known under gate ID {gate_id!r}.")

        return gate

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryGateError(f"Cannot use an empty or blank {field_name}.")
