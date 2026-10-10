from datetime import datetime, timezone

from backend.transformation_diff import LLMTransformationDiffService, StaleDiffError, UnmappedChangeError
from backend.transformation_validation import LLMTransformationValidationService

from .models import APPROVED, PENDING, REJECTED, LLMTransformationApproval


class MissingReviewerError(ValueError):
    """Raised when approve()/reject() is called without a non-empty reviewer."""


class MissingReasonError(ValueError):
    """Raised when reject() is called without a non-empty reason."""


class DiffNotValidatedError(ValueError):
    """Raised when the diff (or its underlying plan) does not currently pass validation."""


class DuplicateDecisionError(ValueError):
    """Raised when approve()/reject() is called for a diff that already has a recorded decision."""


class LLMTransformationApprovalService:
    """Requires an explicit, immutable human decision before a Commit #3 diff may ever be applied.

    Reuses LLMTransformationDiffService.validate() (diff freshness) and
    LLMTransformationValidationService.blocking() (the underlying plan's
    latest validation) as the sole gate: a diff can only be decided while
    both still pass. Once a decision is recorded for a diff_id it is final
    -- approve()/reject() never overwrite it, they raise
    DuplicateDecisionError instead, and the recorded LLMTransformationApproval
    itself is a frozen dataclass. A REJECTED diff must never be applied,
    and an APPROVED one only after this decision exists -- but applying a
    decision is deliberately out of scope here; this service only ever
    records and reports it.
    """

    def __init__(
        self,
        diff_service: LLMTransformationDiffService,
        validation_service: LLMTransformationValidationService,
    ):
        self._diff_service = diff_service
        self._validation_service = validation_service
        self._approvals = {}
        self._history = {}
        self._approval_counter = 0

    def _decide(self, diff_id: str, reviewer: str, status: str, reason) -> LLMTransformationApproval:
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise MissingReviewerError("a reviewer is required to approve or reject a diff")

        if diff_id in self._approvals:
            existing = self._approvals[diff_id]
            raise DuplicateDecisionError(
                f"diff {diff_id!r} was already decided ({existing.status}) by {existing.reviewer!r}"
            )

        diff = self._diff_service.get(diff_id)

        try:
            self._diff_service.validate(diff_id)
        except (StaleDiffError, UnmappedChangeError) as exc:
            raise DiffNotValidatedError(f"diff {diff_id!r} failed validation: {exc}") from exc

        if self._validation_service.blocking(diff.plan_id):
            raise DiffNotValidatedError(
                f"plan {diff.plan_id!r} for diff {diff_id!r} has blocking validation findings"
            )

        self._approval_counter += 1
        approval = LLMTransformationApproval(
            approval_id=f"approval-{diff_id}-{self._approval_counter}",
            diff_id=diff_id,
            reviewer=reviewer,
            status=status,
            reason=reason,
            approved_at=datetime.now(timezone.utc),
        )
        self._approvals[diff_id] = approval
        self._history.setdefault(diff_id, []).append(approval)
        return approval

    def approve(self, diff_id: str, reviewer: str) -> LLMTransformationApproval:
        return self._decide(diff_id, reviewer, APPROVED, reason=None)

    def reject(self, diff_id: str, reviewer: str, reason: str) -> LLMTransformationApproval:
        if not isinstance(reason, str) or not reason.strip():
            raise MissingReasonError("a reason is required to reject a diff")
        return self._decide(diff_id, reviewer, REJECTED, reason=reason)

    def status(self, diff_id: str) -> str:
        self._diff_service.get(diff_id)
        approval = self._approvals.get(diff_id)
        return approval.status if approval else PENDING

    def history(self, diff_id: str) -> tuple:
        self._diff_service.get(diff_id)
        return tuple(self._history.get(diff_id, ()))
