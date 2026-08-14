from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_policy_simulation import (
    ExecutionPolicySimulation,
)

from .execution_policy_simulation_error import (
    ExecutionPolicySimulationError,
)

UNPERMITTED_ACTION_PREFIX = "unpermitted_action:"


class ExecutionPolicySimulationService:
    """
    Previews the enforcement result for an execution session without
    recording an enforcement decision, using an existing execution
    policy precedence service, evaluation service, exception service,
    and enforcement service as the sources of truth for policy
    order, rule violations, active exceptions, and previously
    recorded decisions.

    The service's responsibility is preview only. It never records an
    evaluation, an enforcement decision, or any other state change:
    simulate() reads a policy's violations through the evaluation
    service's pure violations() lookup, never its recording
    evaluate() method, and never calls the enforcement service's
    authorize() or deny().

    Behavior:
    - simulate() resolves the session's policies in precedence order
      and evaluates every one of them, so the same policy set and
      order enforcement would use is what gets previewed
    - A violation is kept unless an active exception exists for its
      exact policy_id, session_id, and rule
    - Violations are always produced in a fixed, sorted order, so
      simulate() is deterministic for the same underlying state
    - compare() looks up a previously recorded enforcement decision
      by decision_id, within the simulation's own session, and
      reports whether the simulation reached the same outcome

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_policy_precedence_service,
        execution_policy_evaluation_service,
        execution_policy_exception_service,
        execution_policy_enforcement_service,
    ):
        """
        Args:
            execution_policy_precedence_service: Read via
                `order(session_id)` for the session's policies, in
                precedence order
            execution_policy_evaluation_service: Read via
                `violations(policy_id, session_id)`, a pure lookup
                that never records an evaluation
            execution_policy_exception_service: Read via
                `active(session_id)` for the exceptions that exempt
                specific violations
            execution_policy_enforcement_service: Read via
                `history(session_id)` so compare() can look up a
                previously recorded decision
        """

        self._execution_policy_precedence_service = execution_policy_precedence_service
        self._execution_policy_evaluation_service = execution_policy_evaluation_service
        self._execution_policy_exception_service = execution_policy_exception_service
        self._execution_policy_enforcement_service = execution_policy_enforcement_service
        self._simulations_by_id = {}
        self._lock = RLock()

    def simulate(self, session_id: str) -> ExecutionPolicySimulation:
        """
        Preview the enforcement result for a session.

        Raises:
            ExecutionPolicySimulationError: If session_id is None or
                blank
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            policy_ids = tuple(self._execution_policy_precedence_service.order(session_id))

            exempted_rules_by_policy = {}

            for exception in self._execution_policy_exception_service.active(session_id):
                exempted_rules_by_policy.setdefault(exception.policy_id, set()).add(exception.rule)

            violations = []

            for policy_id in policy_ids:
                exempted_rules = exempted_rules_by_policy.get(policy_id, set())

                for violation in self._execution_policy_evaluation_service.violations(policy_id, session_id):
                    if self._excepted_rule(violation) in exempted_rules:
                        continue

                    violations.append(f"{policy_id}:{violation}")

            violations = tuple(sorted(violations))

            simulation = ExecutionPolicySimulation(
                simulation_id=str(uuid4()),
                session_id=session_id,
                policies=policy_ids,
                allowed=not violations,
                violations=violations,
                simulated_at=datetime.now(timezone.utc),
            )

            self._simulations_by_id[simulation.simulation_id] = simulation

            return simulation

    def result(self, simulation_id: str) -> ExecutionPolicySimulation:
        """
        Look up a previously produced simulation.

        Raises:
            ExecutionPolicySimulationError: If simulation_id is None
                or blank, or no simulation is recorded under it
        """

        self._validate_text(simulation_id, "simulation ID")

        with self._lock:
            return self._resolve(simulation_id)

    def compare(self, simulation_id: str, decision_id: str) -> bool:
        """
        Compare a simulation against a previously recorded
        enforcement decision for the same session, and report
        whether they reached the same outcome.

        Raises:
            ExecutionPolicySimulationError: If simulation_id or
                decision_id is None or blank, no simulation is
                recorded under simulation_id, or no decision under
                decision_id is recorded for the simulation's session
        """

        self._validate_text(simulation_id, "simulation ID")
        self._validate_text(decision_id, "decision ID")

        with self._lock:
            simulation = self._resolve(simulation_id)

            decision = next(
                (
                    decision
                    for decision in self._execution_policy_enforcement_service.history(simulation.session_id)
                    if decision.decision_id == decision_id
                ),
                None,
            )

            if decision is None:
                raise ExecutionPolicySimulationError(
                    f"No decision is recorded under decision ID {decision_id!r} for session ID {simulation.session_id!r}."
                )

            return simulation.allowed == decision.allowed and simulation.violations == decision.violations

    def _resolve(self, simulation_id: str) -> ExecutionPolicySimulation:
        simulation = self._simulations_by_id.get(simulation_id)

        if simulation is None:
            raise ExecutionPolicySimulationError(f"No simulation is recorded under simulation ID {simulation_id!r}.")

        return simulation

    @staticmethod
    def _excepted_rule(violation: str):
        if violation.startswith(UNPERMITTED_ACTION_PREFIX):
            return violation[len(UNPERMITTED_ACTION_PREFIX) :]

        return None

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicySimulationError(f"Cannot use an empty or blank {field_name}.")
