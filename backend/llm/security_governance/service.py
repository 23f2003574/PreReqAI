from datetime import datetime, timezone

from ..models import LLMRequest, LLMResponse
from ..security_audit import LLMSecurityAuditService
from ..security_gate import LLMSecurityGateService
from ..security_health import LLMSecurityHealthService
from ..security_metrics import LLMSecurityMetricsService
from ..security_policy import BLOCK, LLMSecurityPolicyService

# The start of any request/response's own history for governance purposes:
# using this as a period's lower bound rather than the exact audit
# timestamp means a check_output() governance snapshot reflects the whole
# conversation recorded so far under its request_id (an earlier
# check_input(), plus this call), not only the single record just
# written -- the gate that actually matters before downstream consumption
# is "has anything gone wrong in this exchange yet", not "did this one
# write alone look fine".
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class LLMSecurityGovernanceError(ValueError):
    """Raised by check_input()/check_output() when the governance decision is BLOCK.

    Carries the full structured governance decision -- status, findings,
    security_health, gate_result, audit_reference -- so a caller can
    inspect exactly why, without the blocked request/response ever being
    used further. The audit for this exact decision has already been
    recorded before this is raised (see Rules: "Audit every enforced
    decision").
    """

    def __init__(self, result: dict):
        self.result = result
        super().__init__(f"blocked by LLM security governance: audit {result['audit_reference']!r}")


class LLMSecurityGovernanceService:
    """The single entrypoint unifying Commits #1-#12's security layer --
    input validation -> output validation -> secret handling ->
    sensitive-data policy -> enforcement -> audit -> metrics -> health ->
    approval -- into one deterministic workflow.

    Every field this service returns is produced by an existing service:
    Commit #5's LLMSecurityPolicyService for the enforcement decision
    (itself already composing Commit #1/#2's findings, Commit #3's
    redaction, and Commit #4's sensitive-data policy -- see Rules:
    "Sensitive-data policy is enforced at the existing boundary"),
    Commit #6's LLMSecurityAuditService for the audit record, Commit
    #11's LLMSecurityHealthService for security_health (itself reading
    only Commit #9's metrics), and Commit #12's LLMSecurityGateService
    for gate_result. This service performs no detection, redaction,
    aggregation, or policy evaluation of its own -- it only sequences
    these existing services in the fixed order the Rules specify and
    reshapes their own results into one structured decision (see
    Constraints: "No duplicate policy/security framework").

    check_input()/check_output() enforce at the actual request/response
    boundary: the Commit #5 decision is computed first (input security
    runs before a request would reach a provider; output security runs
    before a response would reach downstream consumption), then
    unconditionally audited -- even a request that goes on to fail
    governance is recorded, per Commit #6's own "failed requests remain
    auditable" rule -- and only then does a BLOCK decision raise
    LLMSecurityGovernanceError (see Rules: "Blocking findings always
    fail governance"). A REDACT decision does not raise: the caller who
    needs the actual redacted payload still calls Commit #5's own
    enforce_input()/enforce_output() directly, exactly as before -- this
    service reports and gates, it does not reimplement redaction.
    Neither method ever weakens or bypasses a Commit #1-#5 decision: a
    BLOCK from those commits is always a BLOCK here too (see
    Constraints: "No automatic remediation or policy weakening").

    evaluate()/decision() are the aggregate governance verdict for a
    scope over a period, meant to gate a protected downstream action
    (e.g. a release, or resuming a paused pipeline) rather than one
    single request (see Rules: "Security gate must pass before
    protected downstream actions"): both run Commit #11's health
    assessment and Commit #12's gate evaluation for the same
    scope/period and report both; decision() is the same computation as
    evaluate() under the name a caller checking whether that action may
    proceed would look for. Every method here is a pure read over
    Commit #6's already-recorded audit trail (aside from Commit #6's own
    record_input()/record_output() append and Commit #12's own gate
    bookkeeping) -- the same underlying audit state always produces the
    same result for a given request/scope/period.
    """

    def __init__(
        self,
        security_policy_service: LLMSecurityPolicyService,
        audit_service: LLMSecurityAuditService,
        metrics_service: LLMSecurityMetricsService,
        health_service: LLMSecurityHealthService,
        gate_service: LLMSecurityGateService,
    ):
        self._security_policy = security_policy_service
        self._audit_service = audit_service
        self._metrics_service = metrics_service
        self._health_service = health_service
        self._gate_service = gate_service

    def _per_request_result(self, request_id: str, policy_decision, audit) -> dict:
        period = (_EPOCH, audit.created_at)
        health = self._health_service.assess(request_id, period)
        gate = self._gate_service.evaluate(request_id, period)

        return {
            "status": policy_decision.action,
            "findings": list(policy_decision.security_findings),
            "security_health": health,
            "gate_result": gate,
            "audit_reference": audit.audit_id,
        }

    def check_input(self, request: LLMRequest, request_id: str) -> dict:
        """Input security -> sensitive-data policy -> audit -> health/gate,
        for one LLMRequest.

        Raises:
            LLMSecurityGovernanceError: If the decision is BLOCK. The
                audit for this decision has already been recorded.
        """
        policy_decision = self._security_policy.check_input(request)
        audit = self._audit_service.record_input(request, request_id, policy_decision)
        result = self._per_request_result(request_id, policy_decision, audit)

        if policy_decision.action == BLOCK:
            raise LLMSecurityGovernanceError(result)
        return result

    def check_output(self, response: LLMResponse, request_id: str) -> dict:
        """Output security -> sensitive-data policy -> audit -> health/gate,
        for one LLMResponse.

        Raises:
            LLMSecurityGovernanceError: If the decision is BLOCK. The
                audit for this decision has already been recorded.
        """
        policy_decision = self._security_policy.check_output(response)
        audit = self._audit_service.record_output(response, request_id, policy_decision)
        result = self._per_request_result(request_id, policy_decision, audit)

        if policy_decision.action == BLOCK:
            raise LLMSecurityGovernanceError(result)
        return result

    def evaluate(self, scope, period) -> dict:
        """The aggregate governance verdict for scope over period."""
        health = self._health_service.assess(scope, period)
        gate = self._gate_service.evaluate(scope, period)
        audit_reference = tuple(
            sorted(audit.audit_id for audit in self._metrics_service.records(scope, period))
        )

        return {
            "status": gate.status,
            "findings": health["findings"],
            "security_health": health,
            "gate_result": gate,
            "audit_reference": audit_reference,
        }

    def decision(self, scope, period) -> dict:
        """The final governance decision for scope over period.

        The same computation as evaluate(), under the name a caller
        deciding whether a protected downstream action may proceed
        would look for.
        """
        return self.evaluate(scope, period)
