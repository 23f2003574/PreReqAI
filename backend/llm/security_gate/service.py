from datetime import datetime, timezone

from ..security_health import CRITICAL, DEGRADED, UNKNOWN, LLMSecurityHealthService
from .models import FAILED, PASSED, LLMSecurityGate


class UnknownGateEvaluationError(KeyError):
    """Raised when passed()/blocking() is called before evaluate() for a scope/period."""


class LLMSecurityGateService:
    """The explicit release/execution gate built on Commit #11's own
    security-health assessment -- no new policy or monitoring framework.

    evaluate() reads LLMSecurityHealthService.assess(scope, period) alone
    and turns its status into one pass/fail verdict, following the Rules
    in a fixed order:

    - UNKNOWN (Commit #11: no recorded decisions for scope/period at
      all) never silently passes -- it fails, the same fail-closed
      default this whole series already uses whenever recognition is
      missing (Commit #4's unpolicied data_type, Commit #5's default
      BLOCK) (see Rules: "UNKNOWN must not silently pass", "Require
      available security-health data")
    - CRITICAL always fails (see Rules: "CRITICAL health -> gate fails")
    - any CRITICAL-severity finding within the assessment -- Commit
      #11's own name for a blocking policy decision (a BLOCK or a
      hard-blocking Commit #1/#2 category) -- fails on its own too,
      independent of the overall status this iteration happened to
      compute (see Rules: "Blocking policy findings -> gate fails")
    - DEGRADED passes only when this service was explicitly configured
      to allow it (`allow_degraded=True` at construction); it fails by
      default (see Rules: "DEGRADED may pass only where existing
      project policy permits" -- the permitting policy is this
      deployment's own explicit, caller-supplied configuration, never
      assumed)
    - HEALTHY passes

    evaluate() never triggers a new health assessment beyond the one
    read, never mutates anything, and makes no policy decision of its
    own -- it only classifies Commit #11's already-computed verdict (see
    Constraints: "No policy changes in this commit"). The same
    underlying audit state therefore always produces the same gate (see
    Rules: "Evaluation is deterministic").

    Mirrors backend.code_patch_gate.LLMCodePatchGateService's own shape:
    evaluate() records one LLMSecurityGate per (scope, period); passed()/
    blocking() then look that recorded gate up rather than re-running the
    assessment, so a caller queries the exact evaluation it asked for.
    """

    def __init__(self, health_service: LLMSecurityHealthService, allow_degraded: bool = False):
        self._health_service = health_service
        self._allow_degraded = allow_degraded
        self._gates_by_key = {}
        self._gate_counter = 0

    @staticmethod
    def _key(scope, period):
        start, end = period
        return (scope, start, end)

    @staticmethod
    def _has_blocking_finding(findings: list) -> bool:
        return any(finding["severity"] == CRITICAL for finding in findings)

    def _status_for(self, health_status: str, findings: list) -> str:
        if health_status in (UNKNOWN, CRITICAL):
            return FAILED
        if self._has_blocking_finding(findings):
            return FAILED
        if health_status == DEGRADED:
            return PASSED if self._allow_degraded else FAILED
        return PASSED

    def evaluate(self, scope, period) -> LLMSecurityGate:
        """Evaluate and record one gate for scope/period.

        Read-only beyond its own gate record: it never triggers a new
        health assessment, security check, or audit write.
        """
        assessment = self._health_service.assess(scope, period)
        status = self._status_for(assessment["status"], assessment["findings"])

        self._gate_counter += 1
        gate = LLMSecurityGate(
            gate_id=f"security-gate-{self._gate_counter}",
            scope=scope,
            status=status,
            findings=assessment["findings"],
            evaluated_at=datetime.now(timezone.utc),
        )
        self._gates_by_key[self._key(scope, period)] = gate
        return gate

    def _tracked(self, scope, period) -> LLMSecurityGate:
        try:
            return self._gates_by_key[self._key(scope, period)]
        except KeyError:
            raise UnknownGateEvaluationError((scope, period))

    def passed(self, scope, period) -> bool:
        """Whether the most recent evaluate() for scope/period was PASSED.

        Raises:
            UnknownGateEvaluationError: If evaluate() has not been called
                for this exact scope/period.
        """
        return self._tracked(scope, period).status == PASSED

    def blocking(self, scope, period) -> bool:
        """Whether the most recent evaluate() for scope/period was FAILED.

        Raises:
            UnknownGateEvaluationError: If evaluate() has not been called
                for this exact scope/period.
        """
        return not self.passed(scope, period)
