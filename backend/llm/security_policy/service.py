import dataclasses

from ..input_security import LLMInputSecurityService
from ..models import LLMRequest, LLMResponse
from ..output_security import SECRETS, LLMOutputSecurityService
from ..secret_redaction import LLMSecretRedactionService
from ..sensitive_data_policy import BLOCK, REDACT, LLMSensitiveDataPolicyService
from .models import ALLOW, LLMPolicyDecision


class LLMSecurityPolicyError(ValueError):
    """Raised by enforce_input()/enforce_output() when a decision is BLOCK.

    Carries the full LLMPolicyDecision so a caller can inspect exactly
    which security findings and/or sensitive-data action caused the
    block, without the blocked request/response ever having been used.
    """

    def __init__(self, decision: LLMPolicyDecision):
        self.decision = decision
        super().__init__(f"blocked by LLM security policy: {decision.reason}")


class LLMSecurityPolicyService:
    """The single enforcement point at the existing LLM request/response
    boundary, composing Commits #1-#4 into one fixed pipeline rather than
    a new one: LLMRequestOrchestrationService.execute() builds and
    validates an LLMRequest before it reaches a provider and returns the
    LLMResponse a provider gives back (see backend.llm.orchestration) --
    check_input()/enforce_input() and check_output()/enforce_output() are
    meant to sit right before and right after exactly that call, without
    this service running requests or talking to a provider itself.

    Both directions follow the same fixed order the Rules specify:
    validate security (Commit #1 for a request, Commit #2 for a
    response) -> apply the sensitive-data policy (Commit #4, itself built
    on Commit #3) -> combine into one allow/redact/block decision (see
    _combine()). A blocking finding for an unsafe instruction or a
    tool/permission-boundary-bypass attempt is never addressable by
    redaction and always forces BLOCK; a blocking SECRETS finding instead
    defers to Commit #4's own action for that data_type, which itself
    still defaults to BLOCK unless an operator has explicitly registered
    otherwise (see Rules: "Blocking policy always wins"). This check runs
    unconditionally: it is never skipped because the content in question
    happens to be a tool-call payload or generated code (see Rules:
    "Never bypass policy for tool calls or generated code") --
    LLMResponse.content is scanned the same way regardless of what it
    encodes.

    enforce_input()/enforce_output() then act on that decision: BLOCK
    raises LLMSecurityPolicyError before the request/response is used
    for anything, so nothing downstream (persistence, context injection,
    a tool-calling or generated-code pipeline) ever sees it; REDACT
    returns a new LLMRequest/LLMResponse of the exact same shape with
    every message/content string passed through Commit #3's
    LLMSecretRedactionService (for a response this is exactly Commit
    #2's own sanitize()); ALLOW returns the request/response completely
    unchanged. Redaction always happens before enforce_input()/
    enforce_output() return, so nothing downstream ever receives
    unredacted content on a REDACT decision -- there is no separate,
    later redaction step to forget to call (see Rules: "Redaction occurs
    before downstream persistence/context injection").
    """

    def __init__(
        self,
        input_security_service: LLMInputSecurityService = None,
        output_security_service: LLMOutputSecurityService = None,
        sensitive_data_policy_service: LLMSensitiveDataPolicyService = None,
        secret_redaction_service: LLMSecretRedactionService = None,
    ):
        self._secret_redaction = secret_redaction_service or LLMSecretRedactionService()
        self._input_security = input_security_service or LLMInputSecurityService(self._secret_redaction)
        self._output_security = output_security_service or LLMOutputSecurityService(self._secret_redaction)
        self._sensitive_data_policy = sensitive_data_policy_service or LLMSensitiveDataPolicyService(
            self._secret_redaction
        )

    @staticmethod
    def _combine(findings: list, sensitive_action: str, policy_ids: list) -> LLMPolicyDecision:
        """Combine one direction's security findings with its sensitive-data
        action into a single decision.

        A blocking finding that is not SECRETS -- an unsafe generated
        instruction or a tool/permission-boundary-bypass attempt -- is
        never addressable by redaction, so it forces BLOCK outright, no
        matter what the sensitive-data policy says (Commit #1 never
        reports SECRETS at all, so every one of its findings is already
        in this category). A blocking SECRETS finding, by contrast, is
        exactly what Commit #4's sensitive-data policy exists to
        arbitrate: its own action for the matched data_type -- BLOCK,
        REDACT, or ALLOW -- is authoritative for that data. This changes
        nothing about Commit #2 used on its own (a secret is still BLOCK
        by default, since an unrecognized/unpolicied data_type itself
        defaults to BLOCK -- see Rules: "Unknown sensitive data must not
        silently become ALLOW"); it only lets an operator-registered
        policy soften that default for a specific, named data_type,
        which is the entire purpose of Commit #4 (see Constraints: "No
        automatic policy weakening" -- nothing here is automatic, it
        requires an explicit registered policy).
        """
        hard_blocking = [
            finding for finding in findings if finding.blocking and finding.category != SECRETS
        ]

        if hard_blocking or sensitive_action == BLOCK:
            reasons = [finding.evidence for finding in hard_blocking]
            if sensitive_action == BLOCK:
                reasons.append("sensitive-data policy requires BLOCK")
            return LLMPolicyDecision(
                action=BLOCK,
                blocking=True,
                security_findings=findings,
                policy_ids=policy_ids,
                reason="; ".join(reasons),
            )

        if sensitive_action == REDACT:
            return LLMPolicyDecision(
                action=REDACT,
                blocking=False,
                security_findings=findings,
                policy_ids=policy_ids,
                reason="sensitive-data policy requires REDACT",
            )

        return LLMPolicyDecision(
            action=ALLOW, blocking=False, security_findings=findings, policy_ids=policy_ids, reason=""
        )

    def check_input(self, request: LLMRequest) -> LLMPolicyDecision:
        """Read-only: validate() Commit #1's findings, then Commit #4's
        sensitive-data action for `request`, combined per the Rules.
        """
        findings = self._input_security.findings(request)
        sensitive_action = self._sensitive_data_policy.evaluate(request)
        policy_ids = self._sensitive_data_policy.applicable_policy_ids(request)
        return self._combine(findings, sensitive_action, policy_ids)

    def check_output(self, response: LLMResponse) -> LLMPolicyDecision:
        """Read-only: Commit #2's findings, then Commit #4's sensitive-data
        action for `response`, combined per the Rules.
        """
        findings = self._output_security.findings(response)
        sensitive_action = self._sensitive_data_policy.evaluate(response)
        policy_ids = self._sensitive_data_policy.applicable_policy_ids(response)
        return self._combine(findings, sensitive_action, policy_ids)

    def _redact_request(self, request: LLMRequest) -> LLMRequest:
        redacted_messages = [
            {**message, "content": self._secret_redaction.redact(message["content"])}
            if isinstance(message.get("content"), str)
            else message
            for message in request.messages
        ]
        return dataclasses.replace(request, messages=redacted_messages)

    def enforce_input(self, request: LLMRequest) -> LLMRequest:
        """Apply check_input()'s decision to `request`.

        Raises:
            LLMSecurityPolicyError: If the decision is BLOCK.

        Returns:
            `request` unchanged (ALLOW), or a redacted copy of it with
            the same model/temperature/max_tokens (REDACT).
        """
        decision = self.check_input(request)
        if decision.action == BLOCK:
            raise LLMSecurityPolicyError(decision)
        if decision.action == REDACT:
            return self._redact_request(request)
        return request

    def enforce_output(self, response: LLMResponse) -> LLMResponse:
        """Apply check_output()'s decision to `response`.

        Raises:
            LLMSecurityPolicyError: If the decision is BLOCK.

        Returns:
            `response` unchanged (ALLOW), or Commit #2's sanitize()d copy
            of it (REDACT).
        """
        decision = self.check_output(response)
        if decision.action == BLOCK:
            raise LLMSecurityPolicyError(decision)
        if decision.action == REDACT:
            return self._output_security.sanitize(response)
        return response
