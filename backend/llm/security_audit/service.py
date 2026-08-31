from datetime import datetime, timezone
from threading import RLock

from ..models import LLMRequest, LLMResponse
from ..security_policy import LLMPolicyDecision
from .models import INPUT, OUTPUT, LLMSecurityAudit


class UnknownAuditError(KeyError):
    """Raised when get()/history() is given a request_id with no recorded audit."""


class LLMSecurityAuditService:
    """Append-only audit trail for Commit #5's policy decisions on both
    sides of the LLM request/response boundary.

    Reuses this codebase's existing audit trail convention
    (LLMRequestAuditService, LLMToolAuditService, LLMTransformationAuditService)
    rather than a second one: record_input()/record_output() each append
    one immutable LLMSecurityAudit snapshot, get() returns the most
    recently recorded snapshot for a request_id, and history() returns
    every snapshot for a request_id in the order recorded -- exactly
    LLMToolAuditService's own get()/history() shape, just keyed the same
    way every audit trail in backend.llm already is: by request_id, the
    identifier LLMRequestOrchestrationService.execute() and every other
    audit service here already use, not a new one invented for this
    trail.

    record_input()/record_output() take the actual LLMRequest/LLMResponse
    Commit #5 checked -- purely so the call site mirrors
    LLMSecurityPolicyService.check_input()/check_output() and so this
    service can confirm what it was actually given -- but never read
    anything from it into the stored record. Only Commit #5's own
    LLMPolicyDecision is: its .action becomes decision, the Commit #4
    policy_ids it names and the Commit #1/#2 finding *categories* (never
    a finding's own evidence text) are the only detail retained (see
    Rules: "Never store raw prompts, responses, secrets, or credentials").

    Nothing recorded here is ever mutated or removed: append is the only
    write this service performs. A request whose Commit #5 check raised
    (BLOCK) is exactly as recordable as one that passed -- record_input()/
    record_output() take the LLMPolicyDecision a caller already has,
    whether or not enforce_input()/enforce_output() went on to raise for
    it (see Rules: "Failed requests remain auditable").
    """

    def __init__(self):
        self._history_by_request = {}
        self._counter = 0
        self._lock = RLock()

    def _record(self, request_id: str, direction: str, decision: LLMPolicyDecision) -> LLMSecurityAudit:
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("Cannot record an audit entry for an empty or blank request_id.")
        if not isinstance(decision, LLMPolicyDecision):
            raise TypeError(
                f"Cannot record something that is not an LLMPolicyDecision: {decision!r}."
            )

        with self._lock:
            self._counter += 1
            audit = LLMSecurityAudit(
                audit_id=f"security-audit-{self._counter}",
                request_id=request_id,
                direction=direction,
                decision=decision.action,
                policy_ids=tuple(decision.policy_ids),
                finding_types=tuple(sorted({finding.category for finding in decision.security_findings})),
                created_at=datetime.now(timezone.utc),
            )
            self._history_by_request.setdefault(request_id, []).append(audit)
            return audit

    def record_input(
        self, request: LLMRequest, request_id: str, decision: LLMPolicyDecision
    ) -> LLMSecurityAudit:
        """Append one INPUT-direction snapshot of `decision` for `request_id`.

        `request` is only type-checked -- neither its messages nor
        anything derived from them is ever stored.
        """
        if not isinstance(request, LLMRequest):
            raise TypeError(f"expected an LLMRequest, got {type(request).__name__}")
        return self._record(request_id, INPUT, decision)

    def record_output(
        self, response: LLMResponse, request_id: str, decision: LLMPolicyDecision
    ) -> LLMSecurityAudit:
        """Append one OUTPUT-direction snapshot of `decision` for `request_id`.

        `response` is only type-checked -- neither its content nor
        anything derived from it is ever stored. This is also the audit
        path for a tool-call proposal or generated code: either arrives
        as an ordinary LLMResponse, so it is recorded the same way as any
        other output, never skipped or routed differently.
        """
        if not isinstance(response, LLMResponse):
            raise TypeError(f"expected an LLMResponse, got {type(response).__name__}")
        return self._record(request_id, OUTPUT, decision)

    def get(self, request_id: str) -> LLMSecurityAudit:
        """The most recently recorded snapshot for `request_id`.

        Raises:
            UnknownAuditError: If nothing has been recorded for `request_id`.
        """
        with self._lock:
            try:
                return self._history_by_request[request_id][-1]
            except KeyError:
                raise UnknownAuditError(request_id)

    def history(self, scope: str) -> list:
        """Every snapshot recorded for `scope` (a request_id), in the order recorded.

        Raises:
            UnknownAuditError: If nothing has been recorded for `scope`.
        """
        with self._lock:
            try:
                return list(self._history_by_request[scope])
            except KeyError:
                raise UnknownAuditError(scope)

    def records(self, scope: str = None) -> tuple:
        """Every snapshot for `scope` (a request_id), or every snapshot ever
        recorded if omitted -- Commit #9's own bulk read for aggregation.

        Mirrors backend.llm.usage.LLMUsageService.records(scope_id) exactly:
        unlike history(), an unrecognized scope yields an empty tuple
        rather than raising -- a scope with nothing recorded is a valid,
        empty result, not an error.
        """
        with self._lock:
            if scope is None:
                return tuple(
                    audit for trail in self._history_by_request.values() for audit in trail
                )
            return tuple(self._history_by_request.get(scope, ()))
