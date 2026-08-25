from datetime import datetime, timezone

from backend.code_transformation import LLMCodeTransformationService
from backend.notebook_analysis import LLMNotebookAnalysisService, NotebookCell
from backend.transformation_approval import APPROVED, LLMTransformationApprovalService
from backend.transformation_diff import LLMTransformationDiffService, StaleDiffError, UnmappedChangeError

from .models import ROLLED_BACK, SUCCEEDED, LLMTransformationExecution


class DiffNotApprovedError(ValueError):
    """Raised when apply() is called for a diff that isn't currently APPROVED."""


class ApplicationNotValidatedError(ValueError):
    """Raised when apply()/rollback() can't proceed because the diff (or the cells
    it targets) no longer matches the source it was generated/applied against."""


class AlreadyAppliedError(ValueError):
    """Raised when apply() is called for a diff that has already been applied."""


class InvalidRollbackStateError(ValueError):
    """Raised when rollback() is called for an execution that isn't currently SUCCEEDED."""


class UnknownExecutionError(KeyError):
    """Raised when looking up an execution_id that was never created."""


class LLMTransformationExecutionService:
    """Applies a Commit #4 approved, validated diff to notebook source -- atomically.

    Reuses LLMTransformationApprovalService.status() (must be APPROVED) and
    LLMTransformationDiffService.validate() (the diff must still be fresh)
    as the sole gate: apply() never touches source for a diff that hasn't
    cleared both. Every cell this diff targets is confirmed present before
    any mutation happens, so a precondition failure -- not approved, stale,
    or a duplicate application -- always leaves source completely
    unchanged. NotebookCell (backend.notebook_analysis, the only
    representation of notebook source this codebase has) is itself
    immutable, so "mutating" a cell means replacing its entry in the
    existing analysis.cells list with a new NotebookCell -- the mechanism
    that list was already built to support; the apply itself is then just
    a sequence of list replacements that cannot partially fail.
    """

    def __init__(
        self,
        approval_service: LLMTransformationApprovalService,
        diff_service: LLMTransformationDiffService,
        transformation_service: LLMCodeTransformationService,
        notebook_analysis_service: LLMNotebookAnalysisService,
    ):
        self._approval_service = approval_service
        self._diff_service = diff_service
        self._transformation_service = transformation_service
        self._notebook_analysis_service = notebook_analysis_service
        self._executions = {}
        self._execution_id_by_diff = {}
        self._execution_counter = 0

    def _load(self, diff):
        plan = self._transformation_service.get(diff.plan_id)
        analysis = self._notebook_analysis_service.get_by_notebook(plan.notebook_id)
        position_by_index = {cell.index: position for position, cell in enumerate(analysis.cells)}
        return analysis, position_by_index

    @staticmethod
    def _replace_source(analysis, position_by_index, cell_index: int, new_source: str) -> str:
        position = position_by_index[cell_index]
        cell = analysis.cells[position]
        original_source = cell.source
        analysis.cells[position] = NotebookCell(index=cell.index, cell_type=cell.cell_type, source=new_source)
        return original_source

    def apply(self, diff_id: str) -> LLMTransformationExecution:
        if diff_id in self._execution_id_by_diff:
            raise AlreadyAppliedError(f"diff {diff_id!r} has already been applied")

        if self._approval_service.status(diff_id) != APPROVED:
            raise DiffNotApprovedError(f"diff {diff_id!r} is not approved")

        try:
            self._diff_service.validate(diff_id)
        except (StaleDiffError, UnmappedChangeError) as exc:
            raise ApplicationNotValidatedError(f"diff {diff_id!r} failed validation: {exc}") from exc

        diff = self._diff_service.get(diff_id)
        analysis, position_by_index = self._load(diff)

        # Every target cell is confirmed present before any mutation -- a
        # missing cell here fails the whole apply() with nothing written.
        for change in diff.changes:
            if change["cell_index"] not in position_by_index:
                raise ApplicationNotValidatedError(
                    f"diff {diff_id!r} targets cell {change['cell_index']}, which no longer exists"
                )

        applied_cells = []
        for change in diff.changes:
            original_source = self._replace_source(
                analysis, position_by_index, change["cell_index"], change["proposed_source"]
            )
            applied_cells.append(
                {
                    "cell_index": change["cell_index"],
                    "original_source": original_source,
                    "applied_source": change["proposed_source"],
                }
            )

        self._execution_counter += 1
        now = datetime.now(timezone.utc)
        execution = LLMTransformationExecution(
            execution_id=f"execution-{diff_id}-{self._execution_counter}",
            diff_id=diff_id,
            status=SUCCEEDED,
            applied_cells=tuple(applied_cells),
            created_at=now,
            completed_at=now,
        )
        self._executions[execution.execution_id] = execution
        self._execution_id_by_diff[diff_id] = execution.execution_id
        return execution

    def _get(self, execution_id: str) -> LLMTransformationExecution:
        try:
            return self._executions[execution_id]
        except KeyError:
            raise UnknownExecutionError(execution_id)

    def status(self, execution_id: str) -> str:
        return self._get(execution_id).status

    def rollback(self, execution_id: str) -> LLMTransformationExecution:
        execution = self._get(execution_id)
        if execution.status != SUCCEEDED:
            raise InvalidRollbackStateError(
                f"execution {execution_id!r} cannot be rolled back from status {execution.status!r}"
            )

        diff = self._diff_service.get(execution.diff_id)
        analysis, position_by_index = self._load(diff)

        missing = [
            applied["cell_index"] for applied in execution.applied_cells if applied["cell_index"] not in position_by_index
        ]
        if missing:
            raise ApplicationNotValidatedError(
                f"cannot rollback execution {execution_id!r}: cells no longer exist: {sorted(missing)}"
            )

        for applied in execution.applied_cells:
            self._replace_source(analysis, position_by_index, applied["cell_index"], applied["original_source"])

        rolled_back = LLMTransformationExecution(
            execution_id=execution.execution_id,
            diff_id=execution.diff_id,
            status=ROLLED_BACK,
            applied_cells=execution.applied_cells,
            created_at=execution.created_at,
            completed_at=datetime.now(timezone.utc),
        )
        self._executions[execution_id] = rolled_back
        return rolled_back
