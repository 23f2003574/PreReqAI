import re
from datetime import datetime, timezone

from backend.code_transformation import LLMCodeTransformationService
from backend.transformation_approval import LLMTransformationApprovalService
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import ROLLED_BACK as EXECUTION_ROLLED_BACK
from backend.transformation_execution import LLMTransformationExecutionService
from backend.transformation_verification import LLMTransformationVerificationService, UnknownVerificationError

from .models import APPLIED, ROLLED_BACK, VERIFICATION_FAILED, VERIFIED, LLMTransformationAudit


class BrokenLifecycleLinkError(ValueError):
    """Raised when the given plan_id/diff_id/execution_id don't actually chain together."""


class MissingApprovalError(ValueError):
    """Raised when the diff being audited has no recorded approval decision."""


class UnknownAuditError(KeyError):
    """Raised when get() is called for an execution_id that was never recorded."""


_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)


def _redact(value: str) -> str:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(value):
            return "[REDACTED]"
    return value


class LLMTransformationAuditService:
    """Records an append-only lifecycle snapshot linking plan, diff,
    approval, execution, and (once available) verification/rollback.

    Reuses every earlier commit's own service purely for reads: record()
    never writes to a plan, diff, approval, execution, or verification --
    it only cross-checks that the given plan_id/diff_id/execution_id
    genuinely chain together (diff.plan_id == plan_id, execution.diff_id
    == diff_id) and that the diff has a recorded approval, then captures
    reviewer/status as of that moment. Calling record() again for the same
    execution -- e.g. after Commit #6 verification or a Commit #9 rollback
    happens -- appends a new, independent snapshot rather than editing the
    old one, so no audit entry is ever mutated once written.
    """

    def __init__(
        self,
        transformation_service: LLMCodeTransformationService,
        diff_service: LLMTransformationDiffService,
        approval_service: LLMTransformationApprovalService,
        execution_service: LLMTransformationExecutionService,
        verification_service: LLMTransformationVerificationService,
    ):
        self._transformation_service = transformation_service
        self._diff_service = diff_service
        self._approval_service = approval_service
        self._execution_service = execution_service
        self._verification_service = verification_service
        self._audits_by_execution = {}
        self._history_by_notebook = {}
        self._audit_counter = 0

    def _resolve_status(self, execution_id: str, execution_status: str) -> str:
        if execution_status == EXECUTION_ROLLED_BACK:
            return ROLLED_BACK

        try:
            has_blocking_findings = self._verification_service.blocking(execution_id)
        except UnknownVerificationError:
            return APPLIED

        return VERIFICATION_FAILED if has_blocking_findings else VERIFIED

    def record(self, plan_id: str, diff_id: str, execution_id: str) -> LLMTransformationAudit:
        plan = self._transformation_service.get(plan_id)
        diff = self._diff_service.get(diff_id)
        execution = self._execution_service.get(execution_id)

        if diff.plan_id != plan_id:
            raise BrokenLifecycleLinkError(f"diff {diff_id!r} does not belong to plan {plan_id!r}")
        if execution.diff_id != diff_id:
            raise BrokenLifecycleLinkError(f"execution {execution_id!r} does not belong to diff {diff_id!r}")

        approval_history = self._approval_service.history(diff_id)
        if not approval_history:
            raise MissingApprovalError(f"diff {diff_id!r} has no recorded approval decision")
        reviewer = approval_history[-1].reviewer

        status = self._resolve_status(execution_id, execution.status)

        self._audit_counter += 1
        audit = LLMTransformationAudit(
            audit_id=f"audit-{execution_id}-{self._audit_counter}",
            plan_id=plan_id,
            diff_id=diff_id,
            execution_id=execution_id,
            reviewer=_redact(reviewer),
            status=status,
            created_at=datetime.now(timezone.utc),
        )
        self._audits_by_execution.setdefault(execution_id, []).append(audit)
        self._history_by_notebook.setdefault(plan.notebook_id, []).append(audit)
        return audit

    def get(self, execution_id: str) -> LLMTransformationAudit:
        """The most recently recorded audit snapshot for this execution."""
        try:
            return self._audits_by_execution[execution_id][-1]
        except (KeyError, IndexError):
            raise UnknownAuditError(execution_id)

    def history(self, notebook_id: str) -> list:
        return list(self._history_by_notebook.get(notebook_id, []))
