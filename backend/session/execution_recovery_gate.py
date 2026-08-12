from dataclasses import (
    dataclass,
    field,
)

from types import (
    MappingProxyType,
)

from uuid import uuid4

from .execution_recovery_gate_error import (
    ExecutionRecoveryGateError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "PENDING",
        "OPEN",
        "BLOCKED",
    }
)


@dataclass(frozen=True)
class ExecutionRecoveryGate:
    """
    Immutable snapshot of the pre-resume checks a session's
    checkpoint must pass before recovery is allowed to proceed.

    The gate is a value object only. It performs no checking of its
    own; creating a gate, running its validation, conflict, and
    checkpoint checks, and looking up whether it is open or which
    checks failed is the responsibility of an execution recovery
    gate service.

    Attributes:
        gate_id: The gate's unique identifier
        session_id: The identifier of the execution session this
            gate guards
        checkpoint_id: The identifier of the checkpoint being gated
        checks: The outcome of each check as of the last evaluation,
            each an immutable mapping with "name", "passed", and
            "reason" (None when passed); empty while PENDING
        status: The gate's current status, one of PENDING, OPEN
            (every check passed; recovery is allowed), or BLOCKED
            (at least one check failed)
    """

    session_id: str

    checkpoint_id: str

    checks: tuple = field(
        default_factory=tuple,
    )

    status: str = "PENDING"

    gate_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.gate_id, "gate ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.checkpoint_id, "checkpoint ID")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionRecoveryGateError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if self.checks is None:
            raise ExecutionRecoveryGateError("Cannot build an execution recovery gate with a None checks.")

        checks_list = [self._normalize_check(check) for check in self.checks]

        object.__setattr__(self, "checks", tuple(checks_list))

        if self.status == "PENDING":
            if self.checks:
                raise ExecutionRecoveryGateError(
                    "Cannot build an execution recovery gate that is PENDING with checks already recorded."
                )
        else:
            if not self.checks:
                raise ExecutionRecoveryGateError(
                    f"Cannot build a {self.status} execution recovery gate with no checks recorded."
                )

            all_passed = all(check["passed"] for check in self.checks)

            if self.status == "OPEN" and not all_passed:
                raise ExecutionRecoveryGateError(
                    "Cannot build an execution recovery gate that is OPEN with a failed check present."
                )

            if self.status == "BLOCKED" and all_passed:
                raise ExecutionRecoveryGateError(
                    "Cannot build an execution recovery gate that is BLOCKED with every check passed."
                )

    def _normalize_check(self, check) -> MappingProxyType:
        if not isinstance(check, dict) and not isinstance(check, MappingProxyType):
            raise ExecutionRecoveryGateError(
                "Cannot build an execution recovery gate with a check that is not a mapping."
            )

        name = check.get("name")
        passed = check.get("passed")
        reason = check.get("reason")

        self._require_text(name, "check name")

        if not isinstance(passed, bool):
            raise ExecutionRecoveryGateError(
                f"Cannot build a check named {name!r} with a non-bool passed."
            )

        if passed and reason is not None:
            raise ExecutionRecoveryGateError(f"Cannot build a passed check named {name!r} with a reason set.")

        if not passed:
            self._require_text(reason, "check reason")

        return MappingProxyType({"name": name, "passed": passed, "reason": reason})

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryGateError(
                f"Cannot build an execution recovery gate with an empty or blank {field_name}."
            )
