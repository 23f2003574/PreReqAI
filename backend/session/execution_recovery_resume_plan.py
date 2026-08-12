from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_recovery_resume_plan_error import (
    ExecutionRecoveryResumePlanError,
)


@dataclass(frozen=True)
class ExecutionRecoveryResumePlan:
    """
    Immutable declaration of where an interrupted execution session
    should continue: a specific checkpoint, and the stage it was
    captured at.

    The plan is a value object only. It performs no resolution of
    its own; creating a plan, resolving a session's active one,
    repointing it at a different checkpoint, and cancelling it is
    the responsibility of an execution recovery resume plan service.

    Attributes:
        plan_id: The plan's unique identifier
        session_id: The identifier of the execution session this
            plan resumes
        checkpoint_id: The identifier of the checkpoint execution
            should resume from
        stage_id: The identifier of the stage the referenced
            checkpoint was captured at
        created_at: When this plan was created
    """

    session_id: str

    checkpoint_id: str

    stage_id: str

    plan_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.plan_id, "plan ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.checkpoint_id, "checkpoint ID")
        self._require_text(self.stage_id, "stage ID")

        if not isinstance(self.created_at, datetime):
            raise ExecutionRecoveryResumePlanError(
                "Cannot build an execution recovery resume plan with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryResumePlanError(
                f"Cannot build an execution recovery resume plan with an empty or blank {field_name}."
            )
