from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_policy_simulation_error import (
    ExecutionPolicySimulationError,
)


@dataclass(frozen=True)
class ExecutionPolicySimulation:
    """
    Immutable record of previewing the enforcement result for a
    session, without recording an enforcement decision.

    The simulation is a value object only. It performs no evaluation
    of its own; resolving precedence, applying active exceptions,
    and producing this preview is the responsibility of an execution
    policy simulation service.

    Attributes:
        simulation_id: The simulation's unique identifier
        session_id: The identifier of the execution session this
            simulation previews
        policies: The identifiers of the policies considered, in the
            precedence order they were considered
        allowed: Whether the session would be authorized, i.e.
            violations is empty
        violations: Every reason execution would be denied, in the
            order they were found. Empty if and only if allowed is
            True
        simulated_at: When this simulation was produced
    """

    simulation_id: str

    session_id: str

    policies: tuple

    allowed: bool

    violations: tuple

    simulated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.simulation_id, "simulation ID")
        self._require_text(self.session_id, "session ID")

        if self.policies is None:
            raise ExecutionPolicySimulationError(
                "Cannot build an execution policy simulation with a None policies."
            )

        policies_list = list(self.policies)

        for policy_id in policies_list:
            if not isinstance(policy_id, str) or not policy_id.strip():
                raise ExecutionPolicySimulationError(
                    "Cannot build an execution policy simulation with a blank policy ID."
                )

        object.__setattr__(self, "policies", tuple(policies_list))

        if not isinstance(self.allowed, bool):
            raise ExecutionPolicySimulationError(
                "Cannot build an execution policy simulation with a non-bool allowed."
            )

        if not isinstance(self.simulated_at, datetime):
            raise ExecutionPolicySimulationError(
                "Cannot build an execution policy simulation with a non-datetime simulated_at."
            )

        if self.violations is None:
            raise ExecutionPolicySimulationError(
                "Cannot build an execution policy simulation with a None violations."
            )

        violations_list = list(self.violations)

        for violation in violations_list:
            if not isinstance(violation, str) or not violation.strip():
                raise ExecutionPolicySimulationError(
                    "Cannot build an execution policy simulation with a blank violation."
                )

        object.__setattr__(self, "violations", tuple(violations_list))

        if self.allowed and violations_list:
            raise ExecutionPolicySimulationError(
                "Cannot build an execution policy simulation that is allowed but has violations."
            )

        if not self.allowed and not violations_list:
            raise ExecutionPolicySimulationError(
                "Cannot build an execution policy simulation that is not allowed but has no violations."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicySimulationError(
                f"Cannot build an execution policy simulation with an empty or blank {field_name}."
            )
