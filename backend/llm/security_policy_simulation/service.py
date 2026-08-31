from ..models import LLMRequest, LLMResponse
from ..secret_redaction import LLMSecretRedactionService
from ..security_policy import BLOCK, LLMSecurityPolicyService
from ..sensitive_data_policy import LLMSensitiveDataPolicyService
from .models import LLMSecurityPolicySimulation


class LLMSecurityPolicySimulationService:
    """Dry-run preview of Commit #5's enforcement for a request or
    response, without ever blocking, redacting, or recording anything.

    Reuses LLMSecurityPolicyService.check_input()/check_output() as the
    sole source of the decision -- both are already read-only (Commit
    #1/#2's findings() and Commit #4's evaluate() neither mutate nor
    persist anything), so this service adds no second policy engine: it
    never re-implements detection, and it never calls
    enforce_input()/enforce_output() (which would raise on BLOCK or
    return a redacted copy) or an LLMSecurityAuditService (Commit #6) --
    a simulation writes no enforcement or audit state at all. The one
    thing beyond the decision itself, the redaction preview, is Commit
    #3's own detect() -- the same scanner Commit #4 already uses -- run
    over exactly the same text Commit #4's evaluate() would resolve (see
    LLMSensitiveDataPolicyService.resolve()), reported as
    {"location", "pattern"} pairs rather than the matched text.

    simulate_input()/simulate_output() only ever read from the
    request/response they are given -- check_input()/check_output() and
    detect() are both pure lookups -- so the payload itself is never
    mutated, and no redacted copy is ever produced or returned; a
    caller who wants an actual redacted copy still calls
    LLMSecurityPolicyService.enforce_input()/enforce_output() themselves.
    """

    def __init__(
        self,
        security_policy_service: LLMSecurityPolicyService = None,
        secret_redaction_service: LLMSecretRedactionService = None,
    ):
        self._secret_redaction = secret_redaction_service or LLMSecretRedactionService()
        self._security_policy = security_policy_service or LLMSecurityPolicyService(
            secret_redaction_service=self._secret_redaction
        )

    def _redactions_for(self, value) -> tuple:
        resolved = LLMSensitiveDataPolicyService.resolve(value)
        return tuple(
            {"location": match["location"], "pattern": match["pattern"]}
            for match in self._secret_redaction.detect(resolved)
        )

    def simulate_input(self, request: LLMRequest) -> LLMSecurityPolicySimulation:
        """Preview what enforce_input(request) would do, without doing it."""
        decision = self._security_policy.check_input(request)
        return LLMSecurityPolicySimulation(
            decision=decision.action,
            policies=tuple(decision.policy_ids),
            findings=tuple(decision.security_findings),
            redactions=self._redactions_for(request),
            would_block=decision.action == BLOCK,
        )

    def simulate_output(self, response: LLMResponse) -> LLMSecurityPolicySimulation:
        """Preview what enforce_output(response) would do, without doing it."""
        decision = self._security_policy.check_output(response)
        return LLMSecurityPolicySimulation(
            decision=decision.action,
            policies=tuple(decision.policy_ids),
            findings=tuple(decision.security_findings),
            redactions=self._redactions_for(response),
            would_block=decision.action == BLOCK,
        )
