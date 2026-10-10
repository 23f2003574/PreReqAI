import difflib
from datetime import datetime, timezone

from backend.code_transformation import LLMCodeTransformationService
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.transformation_validation import LLMTransformationValidationService, UnknownValidationError

from .models import LLMTransformationDiff


class UnvalidatedPlanError(ValueError):
    """Raised when generate() is called for a plan that was never validated."""


class PlanNotValidError(ValueError):
    """Raised when generate() is called for a plan whose validation has blocking findings."""


class UnmappedChangeError(ValueError):
    """Raised when a planned change references a cell that no longer exists,
    so the diff can never be complete."""


class StaleDiffError(ValueError):
    """Raised by validate() when a stored diff's original_source no longer
    matches the notebook's current cell source."""


class UnknownDiffError(KeyError):
    """Raised when looking up a diff_id that was never generated."""


def _unified_diff(cell_index: int, original_source: str, proposed_source: str) -> tuple:
    diff_lines = list(
        difflib.unified_diff(
            original_source.splitlines(keepends=True),
            proposed_source.splitlines(keepends=True),
            fromfile=f"cell_{cell_index}",
            tofile=f"cell_{cell_index}",
        )
    )
    additions = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
    return "".join(diff_lines), additions, deletions


class LLMTransformationDiffService:
    """Turns a validated Commit #2 plan into an explicit, line-level source diff.

    Reuses LLMCodeTransformationService (Commit #1) for the plan itself and
    LLMTransformationValidationService (Commit #2) as the sole gate:
    generate() never diffs a plan that hasn't been validated with no
    blocking findings. Unlike every earlier commit in this series, no new
    LLM call is made here -- a diff between two already-known strings
    (a cell's current source and the plan's own proposed_source) is a
    deterministic text operation, computed with the standard library's
    difflib, and using an LLM for it would only risk an inexact diff.
    generate() only ever reads the plan and the notebook analysis; it never
    writes to either, and never applies a change to notebook source.
    """

    def __init__(
        self,
        transformation_service: LLMCodeTransformationService,
        validation_service: LLMTransformationValidationService,
        notebook_analysis_service: LLMNotebookAnalysisService,
    ):
        self._transformation_service = transformation_service
        self._validation_service = validation_service
        self._notebook_analysis_service = notebook_analysis_service
        self._diffs = {}
        self._diff_counter = 0

    def generate(self, plan_id: str) -> LLMTransformationDiff:
        plan = self._transformation_service.get(plan_id)

        try:
            has_blocking_findings = self._validation_service.blocking(plan_id)
        except UnknownValidationError as exc:
            raise UnvalidatedPlanError(f"plan {plan_id!r} has not been validated") from exc

        if has_blocking_findings:
            raise PlanNotValidError(f"plan {plan_id!r} was validated but has blocking findings")

        analysis = self._notebook_analysis_service.get_by_notebook(plan.notebook_id)
        cells_by_index = {cell.index: cell for cell in analysis.cells}

        changes = []
        total_additions = 0
        total_deletions = 0
        for change in plan.changes:
            cell = cells_by_index.get(change["cell_index"])
            if cell is None:
                raise UnmappedChangeError(
                    f"plan {plan_id!r} has a change for cell {change['cell_index']} that no longer exists"
                )

            unified_diff, additions, deletions = _unified_diff(
                change["cell_index"], cell.source, change["proposed_source"]
            )
            total_additions += additions
            total_deletions += deletions
            changes.append(
                {
                    "cell_index": change["cell_index"],
                    "description": change["description"],
                    "original_source": cell.source,
                    "proposed_source": change["proposed_source"],
                    "unified_diff": unified_diff,
                    "additions": additions,
                    "deletions": deletions,
                }
            )

        self._diff_counter += 1
        diff = LLMTransformationDiff(
            diff_id=f"diff-{plan_id}-{self._diff_counter}",
            plan_id=plan_id,
            changes=tuple(changes),
            additions=total_additions,
            deletions=total_deletions,
            generated_at=datetime.now(timezone.utc),
        )
        self._diffs[diff.diff_id] = diff
        return diff

    def _get(self, diff_id: str) -> LLMTransformationDiff:
        try:
            return self._diffs[diff_id]
        except KeyError:
            raise UnknownDiffError(diff_id)

    def get(self, diff_id: str) -> LLMTransformationDiff:
        """The full stored diff -- lets downstream commits reuse changes/additions/deletions."""
        return self._get(diff_id)

    def validate(self, diff_id: str) -> bool:
        """Re-checks a diff's mappings against the notebook's current analysis.

        Purely deterministic and read-only: a diff built against an earlier
        cell source goes stale if the notebook has since been re-analyzed
        with different content for that cell.
        """
        diff = self._get(diff_id)
        plan = self._transformation_service.get(diff.plan_id)
        analysis = self._notebook_analysis_service.get_by_notebook(plan.notebook_id)
        cells_by_index = {cell.index: cell for cell in analysis.cells}

        for change in diff.changes:
            cell = cells_by_index.get(change["cell_index"])
            if cell is None:
                raise UnmappedChangeError(
                    f"diff {diff_id!r} references cell {change['cell_index']} that no longer exists"
                )
            if cell.source != change["original_source"]:
                raise StaleDiffError(
                    f"diff {diff_id!r} was generated against stale source for cell {change['cell_index']}"
                )

        return True
