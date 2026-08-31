import re

from ..models import LLMRequest
from .models import CRITICAL, PROMPT_INJECTION, TOOL_BOUNDARY_BYPASS, LLMInputSecurityFinding

# Same secret-redaction idiom backend.api_security_review and
# backend.code_patch_security_review already use -- there is no shared
# util module in this repo, every security-review service defines its own
# copy of this trio, so this one does too rather than introducing a new
# shared dependency.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*=\s*['\"][^'\"]+['\"]"),
)

# Unambiguous attempts to override the system prompt or existing
# instructions. Each entry is (pattern, human-readable description).
_PROMPT_INJECTION_PATTERNS = (
    (re.compile(r"(?i)ignore (all |any )?(previous|prior|above|earlier) instructions"),
     "instructs the model to ignore its previous instructions"),
    (re.compile(r"(?i)disregard (all |any )?(previous|prior|above|earlier) (instructions|prompts?)"),
     "instructs the model to disregard its previous instructions"),
    (re.compile(r"(?i)forget (all |any )?(previous|prior|your) instructions"),
     "instructs the model to forget its previous instructions"),
    (re.compile(r"(?i)ignore (the )?system prompt"),
     "instructs the model to ignore its system prompt"),
    (re.compile(r"(?i)(reveal|print|repeat) (your|the) (system prompt|hidden instructions)"),
     "attempts to extract the system prompt"),
    (re.compile(r"(?i)you are now (DAN|in developer mode|unrestricted|jailbroken)"),
     "attempts a known jailbreak persona override"),
    (re.compile(r"(?i)do anything now"),
     "attempts a known jailbreak persona override"),
    (re.compile(r"(?i)pretend (you|that you) (are|have) no (restrictions|rules|limitations)"),
     "instructs the model to pretend it has no restrictions"),
)

# Unambiguous attempts to get the model to circumvent tool/permission
# enforcement. This service only flags the attempt in the prompt text --
# the actual authorization decision remains LLMToolPermissionService's,
# which this does not duplicate or re-implement.
_TOOL_BOUNDARY_PATTERNS = (
    (re.compile(r"(?i)bypass (the )?(tool |permission )?(permission|policy|check)"),
     "instructs the model to bypass a permission check"),
    (re.compile(r"(?i)ignore (tool|permission) (polic(y|ies)|checks?)"),
     "instructs the model to ignore tool/permission policy"),
    (re.compile(r"(?i)disable (the )?(permission|safety|security) (check|checks|system)"),
     "instructs the model to disable a permission/safety check"),
    (re.compile(r"(?i)grant (yourself|me) (access|permission|admin)"),
     "instructs the model to self-grant access"),
    (re.compile(r"(?i)escalate (your |my )?privileges"),
     "instructs the model to escalate privileges"),
    (re.compile(r"(?i)act as (an? )?(admin|root|superuser)"),
     "instructs the model to assume an administrative identity"),
    (re.compile(r"(?i)without (any )?authoriz(ation|ing)"),
     "instructs the model to act without authorization"),
)


class LLMInputSecurityError(ValueError):
    """Raised by validate() when a request carries a blocking finding.

    Carries every finding (not just the blocking ones) so a caller can
    report the full picture, the same way backend.input_validation's
    ValidationFailedError carries every violation rather than just the
    first.
    """

    def __init__(self, findings: list):
        self.findings = findings
        blocking = [finding for finding in findings if finding.blocking]
        summary = "; ".join(f"{finding.category}: {finding.evidence}" for finding in blocking)
        super().__init__(f"LLM request failed input security validation: {summary}")


def _redact(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


class LLMInputSecurityService:
    """Deterministic, read-only security screen for an LLMRequest, run
    before it reaches LLMRequestOrchestrationService.execute().

    Takes the same LLMRequest the orchestration pipeline already builds
    and validates -- this introduces no new request or message shape.
    validate() first reuses LLMRequest.validate() for structural checks,
    then scans each message's content for unambiguous prompt-injection
    and tool/permission-boundary-bypass indicators via fixed pattern
    matches; it never calls an LLM, never mutates the request or any
    message, and never modifies a prompt automatically. Findings mirror
    the category/severity/evidence shape backend.api_security_review and
    backend.code_patch_security_review already use, and reuse their
    redact-before-store convention: evidence is always drawn from
    already-redacted content, so a finding can never itself leak a
    credential or other sensitive value present in the input.
    """

    def _findings_for_message(self, role: str, content: str) -> list:
        sanitized = _redact(content)
        findings = []

        for pattern, description in _PROMPT_INJECTION_PATTERNS:
            if pattern.search(sanitized):
                findings.append(
                    LLMInputSecurityFinding(
                        category=PROMPT_INJECTION,
                        severity=CRITICAL,
                        evidence=f"{role} message {description}: {sanitized!r}",
                        blocking=True,
                    )
                )

        for pattern, description in _TOOL_BOUNDARY_PATTERNS:
            if pattern.search(sanitized):
                findings.append(
                    LLMInputSecurityFinding(
                        category=TOOL_BOUNDARY_BYPASS,
                        severity=CRITICAL,
                        evidence=f"{role} message {description}: {sanitized!r}",
                        blocking=True,
                    )
                )

        return findings

    def findings(self, request: LLMRequest) -> list:
        """Every security finding for `request`, computed fresh each call.

        Purely a function of the request's own messages -- nothing is
        cached or stored, so this can be called any number of times
        without state to keep in sync.
        """
        found = []
        for message in request.messages:
            content = message.get("content")
            if not isinstance(content, str):
                continue
            found.extend(self._findings_for_message(message.get("role", ""), content))
        return found

    def allowed(self, request: LLMRequest) -> bool:
        """Whether `request` may proceed: no finding blocks it."""
        return not any(finding.blocking for finding in self.findings(request))

    def validate(self, request: LLMRequest) -> bool:
        """Raise if `request` may not proceed; return True if it may.

        Raises:
            LLMInputSecurityError: If any finding is blocking.
        """
        request.validate()

        found = self.findings(request)
        if any(finding.blocking for finding in found):
            raise LLMInputSecurityError(found)
        return True
