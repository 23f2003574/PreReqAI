from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_storage_decision_error import (
    ExecutionStorageDecisionError,
)


@dataclass(frozen=True)
class ExecutionStorageDecision:
    """
    Immutable record of a single decision made by the storage
    orchestration pipeline for a volume, on behalf of a runtime.

    The decision is a value object only. It performs no evaluation of
    its own; provisioning, mounting, evaluating, failing over, and
    releasing volumes -- and deciding whether each is allowed -- is
    the responsibility of an execution storage orchestration service,
    which produces a new record for every action rather than mutating
    an existing one.

    Attributes:
        decision_id: The decision's unique identifier
        runtime_id: The runtime this decision was made on behalf of
        volume_id: The volume this decision concerns
        target: The storage target selected by this decision, or None
            when no target selection was part of it
        allowed: Whether the action this decision represents was
            permitted to proceed
        reason: Why the decision came out the way it did
        created_at: When the decision was made
    """

    decision_id: str

    runtime_id: str

    volume_id: str

    target: str

    allowed: bool

    reason: str

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.decision_id, "decision ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.volume_id, "volume ID")
        self._require_text(self.reason, "reason")

        if self.target is not None and (not isinstance(self.target, str) or not self.target.strip()):
            raise ExecutionStorageDecisionError(
                "Cannot build an execution storage decision with a blank target."
            )

        if not isinstance(self.allowed, bool):
            raise ExecutionStorageDecisionError(
                f"Cannot build an execution storage decision with a non-boolean allowed: "
                f"{self.allowed!r}."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ExecutionStorageDecisionError(
                "Cannot build an execution storage decision with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageDecisionError(
                f"Cannot build an execution storage decision with an empty or blank {field_name}."
            )
