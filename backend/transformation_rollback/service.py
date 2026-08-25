from datetime import datetime, timezone

from backend.code_transformation import LLMCodeTransformationService
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import SUCCEEDED as EXECUTION_SUCCEEDED
from backend.transformation_execution import InvalidRollbackStateError, LLMTransformationExecutionService

from .models import RESTORED, LLMTransformationRollback


class MissingReasonError(ValueError):
    """Raised when rollback() is called without a non-empty reason."""


class ExecutionNotAppliedError(ValueError):
    """Raised when rollback() is called for an execution that isn't currently SUCCEEDED."""


class AlreadyRolledBackError(ValueError):
    """Raised when rollback() is called for an execution that has already been restored."""


class UnknownRollbackError(KeyError):
    """Raised when status() is called for a rollback_id that was never created."""


class LLMTransformationRollbackService:
    """Safely restores an applied execution's original source, with a
    recorded, mandatory reason -- typically a Commit #6 verification
    failure or a Commit #7 critical regression.

    Reuses LLMTransformationExecutionService.rollback() (Commit #5) as the
    actual atomic source-restoration mechanism -- this service never
    touches notebook source, applied_cells, or the compiler itself; it only
    wraps that call with a mandatory reason, an immutable audit record, and
    a notebook-scoped history(). Every precondition -- missing reason, not
    applied, already restored -- is checked before Commit #5's own
    rollback() is ever invoked, so a rejected attempt here always leaves
    source untouched, same as Commit #5's own atomicity guarantee.
    """

    def __init__(
        self,
        execution_service: LLMTransformationExecutionService,
        diff_service: LLMTransformationDiffService,
        transformation_service: LLMCodeTransformationService,
    ):
        self._execution_service = execution_service
        self._diff_service = diff_service
        self._transformation_service = transformation_service
        self._rollback_by_execution = {}
        self._rollbacks_by_id = {}
        self._history_by_notebook = {}
        self._rollback_counter = 0

    def _notebook_id_for(self, execution) -> str:
        diff = self._diff_service.get(execution.diff_id)
        plan = self._transformation_service.get(diff.plan_id)
        return plan.notebook_id

    def rollback(self, execution_id: str, reason: str) -> LLMTransformationRollback:
        if not isinstance(reason, str) or not reason.strip():
            raise MissingReasonError("a reason is required to roll back a transformation")

        execution = self._execution_service.get(execution_id)

        if execution_id in self._rollback_by_execution:
            raise AlreadyRolledBackError(f"execution {execution_id!r} has already been restored")

        if execution.status != EXECUTION_SUCCEEDED:
            raise ExecutionNotAppliedError(
                f"execution {execution_id!r} is not an applied transformation (status={execution.status!r})"
            )

        notebook_id = self._notebook_id_for(execution)

        try:
            self._execution_service.rollback(execution_id)
        except InvalidRollbackStateError as exc:
            raise AlreadyRolledBackError(f"execution {execution_id!r} has already been restored") from exc

        self._rollback_counter += 1
        rollback_record = LLMTransformationRollback(
            rollback_id=f"rollback-{execution_id}-{self._rollback_counter}",
            execution_id=execution_id,
            reason=reason,
            status=RESTORED,
            restored_at=datetime.now(timezone.utc),
        )
        self._rollback_by_execution[execution_id] = rollback_record
        self._rollbacks_by_id[rollback_record.rollback_id] = rollback_record
        self._history_by_notebook.setdefault(notebook_id, []).append(rollback_record)
        return rollback_record

    def status(self, rollback_id: str) -> str:
        try:
            return self._rollbacks_by_id[rollback_id].status
        except KeyError:
            raise UnknownRollbackError(rollback_id)

    def history(self, notebook_id: str) -> list:
        return list(self._history_by_notebook.get(notebook_id, []))
