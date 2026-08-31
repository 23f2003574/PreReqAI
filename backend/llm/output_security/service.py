import dataclasses
import re

from ..models import LLMResponse
from ..secret_redaction import LLMSecretRedactionService
from .models import CRITICAL, SECRETS, TOOL_BOUNDARY_BYPASS, UNSAFE_INSTRUCTION, LLMOutputSecurityFinding

# The same dangerous-construct list backend.api_security_review,
# backend.code_patch_security_review, and backend.generated_code_review
# already treat as unsafe in generated output -- reused verbatim rather
# than re-deciding what "unsafe" means a fourth time.
_DANGEROUS_PATTERNS = (
    ("eval(", "eval() can execute arbitrary code"),
    ("exec(", "exec() can execute arbitrary code"),
    ("os.system(", "os.system() can execute arbitrary shell commands"),
    ("subprocess.", "subprocess usage can execute arbitrary shell commands"),
    ("pickle.loads(", "pickle.loads() can execute arbitrary code from untrusted input"),
    ("__import__(", "dynamic __import__ can load arbitrary modules"),
)

# Unambiguous generated suggestions to circumvent tool/permission
# enforcement -- the output-side mirror of
# backend.llm.input_security's request-side patterns. This service only
# flags the suggestion in generated text -- the actual authorization
# decision remains LLMToolPermissionService's, which this does not
# duplicate or re-implement.
_TOOL_BOUNDARY_PATTERNS = (
    (re.compile(r"(?i)bypass (the )?(tool |permission )?(permission|policy|check)"),
     "suggests bypassing a permission check"),
    (re.compile(r"(?i)disable (the )?(permission|safety|security) (check|checks|system)"),
     "suggests disabling a permission/safety check"),
    (re.compile(r"(?i)grant (yourself|me) (access|permission|admin)"),
     "suggests self-granting access"),
    (re.compile(r"(?i)escalate (your |my )?privileges"),
     "suggests escalating privileges"),
    (re.compile(r"(?i)act as (an? )?(admin|root|superuser)"),
     "suggests assuming an administrative identity"),
    (re.compile(r"(?i)without (any )?authoriz(ation|ing)"),
     "suggests acting without authorization"),
)


class MalformedOutputError(ValueError):
    """Raised when a value given to LLMOutputSecurityService isn't a usable LLMResponse."""


class LLMOutputSecurityError(ValueError):
    """Raised by validate() when a response carries a blocking finding.

    Carries every finding (not just the blocking ones) so a caller can
    report the full picture, the same way
    backend.llm.input_security.LLMInputSecurityError carries every
    finding on the request side.
    """

    def __init__(self, findings: list):
        self.findings = findings
        blocking = [finding for finding in findings if finding.blocking]
        summary = "; ".join(f"{finding.category}: {finding.evidence}" for finding in blocking)
        super().__init__(f"LLM response failed output security validation: {summary}")


class LLMOutputSecurityService:
    """Deterministic, read-only security screen for an LLMResponse, run
    before its content may be returned to a user or handed to a
    downstream project workflow.

    Takes the same LLMResponse LLMRequestOrchestrationService.execute()
    already returns -- this introduces no new response shape. findings()
    scans response.content for unambiguous secret/credential leakage,
    dangerous generated-code constructs, and tool/permission-boundary-
    bypass suggestions via fixed pattern matches; it never calls an LLM
    and never executes, evaluates, or applies anything the response
    contains. Findings mirror the category/severity/evidence shape
    backend.api_security_review and backend.code_patch_security_review
    already use. Secret detection and redaction are both delegated to
    Commit #3's LLMSecretRedactionService rather than a local copy:
    evidence is always drawn from already-redacted content, so a finding
    can never itself leak the credential it flags, and sanitize() applies
    that same redaction to the response's content and nothing else -- it
    never reformats, reparses, or otherwise restructures the content, so
    already-structured output (e.g. JSON) survives with every field but
    the redacted secret unchanged.
    """

    def __init__(self, secret_redaction_service: LLMSecretRedactionService = None):
        self._secret_redaction = secret_redaction_service or LLMSecretRedactionService()

    @staticmethod
    def _content(response) -> str:
        if not isinstance(response, LLMResponse):
            raise MalformedOutputError(
                f"expected an LLMResponse, got {type(response).__name__}"
            )
        if not isinstance(response.content, str) or not response.content.strip():
            raise MalformedOutputError("LLMResponse.content must be a non-empty string")
        return response.content

    def findings(self, response: LLMResponse) -> list:
        """Every security finding for `response`, computed fresh each call.

        Purely a function of the response's own content -- nothing is
        cached or stored, so this can be called any number of times
        without state to keep in sync.

        Raises:
            MalformedOutputError: If `response` is not an LLMResponse with
                non-empty string content.
        """
        content = self._content(response)
        sanitized = self._secret_redaction.redact(content)
        found = []

        for match in self._secret_redaction.detect(content):
            found.append(
                LLMOutputSecurityFinding(
                    category=SECRETS,
                    severity=CRITICAL,
                    evidence=(
                        f"response content matches a known secret/credential pattern "
                        f"({match['pattern']}): {sanitized!r}"
                    ),
                    blocking=True,
                )
            )

        for needle, description in _DANGEROUS_PATTERNS:
            if needle in sanitized:
                found.append(
                    LLMOutputSecurityFinding(
                        category=UNSAFE_INSTRUCTION,
                        severity=CRITICAL,
                        evidence=f"generated output uses {needle.rstrip('(').rstrip('.')}: {description}",
                        blocking=True,
                    )
                )

        for pattern, description in _TOOL_BOUNDARY_PATTERNS:
            if pattern.search(sanitized):
                found.append(
                    LLMOutputSecurityFinding(
                        category=TOOL_BOUNDARY_BYPASS,
                        severity=CRITICAL,
                        evidence=f"generated output {description}: {sanitized!r}",
                        blocking=True,
                    )
                )

        return found

    def allowed(self, response: LLMResponse) -> bool:
        """Whether `response` may proceed downstream: no finding blocks it."""
        return not any(finding.blocking for finding in self.findings(response))

    def validate(self, response: LLMResponse) -> bool:
        """Raise if `response` may not proceed downstream; return True if it may.

        Raises:
            MalformedOutputError: If `response` is not a usable LLMResponse.
            LLMOutputSecurityError: If any finding is blocking.
        """
        found = self.findings(response)
        if any(finding.blocking for finding in found):
            raise LLMOutputSecurityError(found)
        return True

    def sanitize(self, response: LLMResponse) -> LLMResponse:
        """A copy of `response` with any secret/credential pattern redacted.

        Only response.content is touched, and only by substring
        replacement -- model/usage/finish_reason are carried over
        unchanged, and nothing is reparsed or reformatted, so
        already-structured content (e.g. JSON) keeps every field except
        the redacted secret value exactly as given.
        """
        content = self._content(response)
        return dataclasses.replace(response, content=self._secret_redaction.redact(content))
