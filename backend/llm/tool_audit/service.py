import dataclasses
import re
from datetime import datetime, timezone

from ..tool_execution import LLMToolExecution
from ..tool_invocation import LLMToolInvocationPlan
from ..tool_permissions import LLMToolAuthorization
from .models import PLANNED, STATUSES, LLMToolAudit

# Same secret-redaction convention used by backend.transformation_audit
# (which redacts its reviewer the same way), backend.api_recommendation_export,
# backend.llm.tool_execution, and backend.llm.tool_results.
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


class UnknownAuditError(KeyError):
    """Raised when looking up a plan_id/execution_id/request_id with no trail."""


class DuplicateAuditPlanError(ValueError):
    """Raised when start() is called twice for the same plan_id."""


class BrokenLifecycleLinkError(ValueError):
    """Raised when an execution does not chain back to a started plan.

    Named and used as in backend.transformation_audit: the audit trail
    refuses to record a link it cannot verify, rather than inventing one.
    """


class LLMToolAuditService:
    """Append-only audit trail for the lifecycle of one LLM-generated tool call.

    Reuses the codebase's existing audit conventions rather than adding a
    second framework. It is the tool-calling counterpart of
    LLMRequestAuditService, with the same shape -- start/record/complete
    appending immutable snapshots, get() returning the most recent one,
    history() returning the whole trail -- and it borrows
    LLMTransformationAuditService's lifecycle-linking discipline: an
    execution is only recorded once its plan_id is known to chain back to a
    started plan, and identity fields are redacted on the way in.

    Every status other than PLANNED comes from the service that decided it:
    Commit #4's authorization decisions and Commit #5's execution statuses.
    This service records facts; it never re-derives them, never mutates the
    plan/execution it reads, and never runs anything.
    """

    def __init__(self):
        self._trails_by_plan = {}
        self._audits_by_execution = {}
        self._history_by_request = {}
        self._plan_by_execution = {}
        self._audit_counter = 0

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _normalize_subject(subject) -> str:
        """A subject as one redacted string, however the caller expressed it.

        Commit #4 accepts a single identity or a collection of scopes; both
        are recorded here in a single, stable form.
        """
        if subject is None:
            return None
        if isinstance(subject, str):
            return _redact(subject)
        if isinstance(subject, (list, tuple, set, frozenset)):
            return ",".join(sorted(_redact(str(item)) for item in subject))
        return _redact(str(subject))

    def _append(self, audit: LLMToolAudit) -> LLMToolAudit:
        self._trails_by_plan[audit.plan_id].append(audit)
        self._history_by_request.setdefault(audit.request_id, []).append(audit)
        if audit.execution_id is not None:
            self._audits_by_execution.setdefault(audit.execution_id, []).append(audit)
        return audit

    def _next_audit_id(self, scope: str) -> str:
        self._audit_counter += 1
        return f"audit-{scope}-{self._audit_counter}"

    def _latest_for_plan(self, plan_id: str) -> LLMToolAudit:
        try:
            return self._trails_by_plan[plan_id][-1]
        except KeyError:
            raise UnknownAuditError(plan_id)

    # -- lifecycle ---------------------------------------------------------

    def start(self, plan, request_id: str, subject=None, authorization=None) -> LLMToolAudit:
        """Open a trail for one validated invocation plan.

        request_id and subject are parameters rather than being read off the
        plan because an LLMToolInvocationPlan carries neither -- it records
        what the model asked for, not which conversation asked or on whose
        behalf. Both are needed to link request -> plan -> execution, so
        both are supplied by the caller that knows them.
        """
        if not isinstance(plan, LLMToolInvocationPlan):
            raise TypeError(
                f"Cannot audit something that is not an LLMToolInvocationPlan: {plan!r}."
            )

        if not request_id or not isinstance(request_id, str):
            raise ValueError("request_id is required")

        if plan.plan_id in self._trails_by_plan:
            raise DuplicateAuditPlanError(
                f"an audit trail already exists for plan_id {plan.plan_id!r}"
            )

        self._trails_by_plan[plan.plan_id] = []

        audit = LLMToolAudit(
            audit_id=self._next_audit_id(plan.plan_id),
            request_id=request_id,
            plan_id=plan.plan_id,
            execution_id=None,
            tool_name=plan.tool_name,
            subject=self._normalize_subject(subject),
            status=PLANNED,
            reason=_redact(plan.rationale) if plan.rationale else None,
            created_at=datetime.now(timezone.utc),
        )
        self._append(audit)

        if authorization is not None:
            return self.record_authorization(plan.plan_id, authorization)
        return audit

    def record_authorization(self, plan_id: str, authorization) -> LLMToolAudit:
        """Append the Commit #4 authorization outcome for a started plan."""
        if not isinstance(authorization, LLMToolAuthorization):
            raise TypeError(
                f"Cannot record something that is not an LLMToolAuthorization: "
                f"{authorization!r}."
            )

        previous = self._latest_for_plan(plan_id)

        audit = dataclasses.replace(
            previous,
            audit_id=self._next_audit_id(plan_id),
            status=authorization.decision,
            authorization=authorization.decision,
            authorization_policy_id=authorization.policy_id,
            reason=_redact(authorization.reason) if authorization.reason else None,
        )
        return self._append(audit)

    def record_execution(self, execution) -> LLMToolAudit:
        """Append the Commit #5 execution attempt, linking it to its plan.

        Refuses an execution whose plan was never started here -- an audit
        trail that cannot verify the link does not record one.
        """
        if not isinstance(execution, LLMToolExecution):
            raise TypeError(
                f"Cannot record something that is not an LLMToolExecution: {execution!r}."
            )

        if execution.plan_id not in self._trails_by_plan:
            raise BrokenLifecycleLinkError(
                f"execution {execution.execution_id!r} references plan "
                f"{execution.plan_id!r}, which has no audit trail"
            )

        known_plan = self._plan_by_execution.get(execution.execution_id)
        if known_plan is not None and known_plan != execution.plan_id:
            raise BrokenLifecycleLinkError(
                f"execution {execution.execution_id!r} is already recorded against "
                f"plan {known_plan!r}, not {execution.plan_id!r}"
            )

        previous = self._latest_for_plan(execution.plan_id)
        self._plan_by_execution[execution.execution_id] = execution.plan_id

        audit = dataclasses.replace(
            previous,
            audit_id=self._next_audit_id(execution.execution_id),
            execution_id=execution.execution_id,
            status=execution.status,
            reason=_redact(execution.error) if execution.error else None,
            completed_at=execution.completed_at,
        )
        return self._append(audit)

    def complete(self, execution_id: str, status: str) -> LLMToolAudit:
        """Append the terminal snapshot for a recorded execution."""
        if status not in STATUSES:
            raise ValueError(
                f"status {status!r} is not one of {sorted(STATUSES)}"
            )

        try:
            plan_id = self._plan_by_execution[execution_id]
        except KeyError:
            raise UnknownAuditError(execution_id)

        previous = self._latest_for_plan(plan_id)

        audit = dataclasses.replace(
            previous,
            audit_id=self._next_audit_id(execution_id),
            execution_id=execution_id,
            status=status,
            completed_at=datetime.now(timezone.utc),
        )
        return self._append(audit)

    # -- reads -------------------------------------------------------------

    def get(self, execution_id: str) -> LLMToolAudit:
        """The most recent snapshot for one execution."""
        try:
            return self._audits_by_execution[execution_id][-1]
        except KeyError:
            raise UnknownAuditError(execution_id)

    def history(self, request_id: str) -> list:
        """Every snapshot recorded for one conversation, in the order taken."""
        try:
            return list(self._history_by_request[request_id])
        except KeyError:
            raise UnknownAuditError(request_id)

    def trail(self, plan_id: str) -> list:
        """Every snapshot recorded for one plan, in the order taken."""
        try:
            return list(self._trails_by_plan[plan_id])
        except KeyError:
            raise UnknownAuditError(plan_id)
