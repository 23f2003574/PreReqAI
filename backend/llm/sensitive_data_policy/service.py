from threading import RLock

from ..models import LLMRequest, LLMResponse
from ..secret_redaction import LLMSecretRedactionService
from .models import ALLOW, BLOCK, REDACT, InvalidSensitiveDataPolicyError, LLMSensitiveDataPolicy

# Precedence when a value matches more than one data_type: BLOCK beats
# REDACT beats ALLOW (see Rules: "Explicit BLOCK overrides REDACT").
_ACTION_RANK = {ALLOW: 0, REDACT: 1, BLOCK: 2}


class DuplicatePolicyError(InvalidSensitiveDataPolicyError):
    """Raised when register() is called twice for the same data_type."""


class UnknownDataTypeError(KeyError):
    """Raised when get() is called for a data_type with no registered policy."""


class LLMSensitiveDataPolicyService:
    """Decides whether sensitive data detected in an LLM-bound or
    LLM-generated value may pass, must be redacted, or must be blocked.

    Builds directly on Commit #3's LLMSecretRedactionService rather than a
    second scanner: data_type is exactly one of the categories that
    service's detect() already reports (its match "pattern" values), so
    evaluate() never invents its own detection -- it only decides the
    *action* for data a scanner already found. evaluate() and allowed()
    also reuse Commit #1's LLMRequest and Commit #2's LLMResponse
    directly: passing either one in is resolved to the text it actually
    carries (every string message content for a request, the response
    content for a response) before scanning, so the same policy applies
    consistently on both the input and the output side of the pipeline
    without a separate code path for each.

    A value with no detected sensitive data at all is ALLOW by default.
    A value whose detected data_type has no registered, enabled policy is
    BLOCK by default (see Rules: "Unknown sensitive data must not
    silently become ALLOW") -- the opposite default from
    backend.session.ExecutionPolicyRiskThresholdService, which defaults
    an unmatched risk score to ALLOW: here, failing to recognize a
    sensitive-data category is exactly the situation that must fail
    closed instead. When a value matches more than one data_type, the
    single most restrictive action wins: BLOCK beats REDACT beats ALLOW.

    This service never stores or returns the sensitive value itself --
    only actions and data_type labels (see Commit #3's own guarantee that
    a match never carries the matched text).
    """

    def __init__(self, secret_redaction_service: LLMSecretRedactionService = None):
        self._secret_redaction = secret_redaction_service or LLMSecretRedactionService()
        self._policies_by_data_type = {}
        self._lock = RLock()

    def register(self, policy: LLMSensitiveDataPolicy) -> LLMSensitiveDataPolicy:
        """Register a policy for its data_type.

        Raises:
            InvalidSensitiveDataPolicyError: If policy is not an
                LLMSensitiveDataPolicy.
            DuplicatePolicyError: If a policy is already registered for
                that data_type.
        """
        if not isinstance(policy, LLMSensitiveDataPolicy):
            raise InvalidSensitiveDataPolicyError(
                f"Cannot register a policy that is not an LLMSensitiveDataPolicy: {policy!r}."
            )

        with self._lock:
            if policy.data_type in self._policies_by_data_type:
                raise DuplicatePolicyError(
                    f"A policy is already registered for data_type {policy.data_type!r}."
                )
            self._policies_by_data_type[policy.data_type] = policy
            return policy

    def get(self, data_type: str) -> LLMSensitiveDataPolicy:
        """The registered policy for `data_type`.

        Raises:
            UnknownDataTypeError: If no policy is registered for `data_type`.
        """
        with self._lock:
            try:
                return self._policies_by_data_type[data_type]
            except KeyError:
                raise UnknownDataTypeError(data_type)

    def _action_for(self, data_type: str) -> str:
        with self._lock:
            policy = self._policies_by_data_type.get(data_type)
        # An unregistered or disabled policy is never a silent ALLOW.
        if policy is None or not policy.enabled:
            return BLOCK
        return policy.action

    @staticmethod
    def _resolve(value):
        """Reduce an LLMRequest/LLMResponse to the text it actually carries.

        Any other value (a bare string, or structured data such as a
        tool-call argument dict) is passed straight through to Commit
        #3's own recursive detect(), unchanged.
        """
        if isinstance(value, LLMRequest):
            return [
                message.get("content")
                for message in value.messages
                if isinstance(message.get("content"), str)
            ]
        if isinstance(value, LLMResponse):
            return value.content
        return value

    @staticmethod
    def resolve(value):
        """Public entry point for the same LLMRequest/LLMResponse reduction
        evaluate()/applicable_policy_ids() already use internally.

        Reused directly by Commit #7's LLMSecurityPolicySimulationService
        so its redaction preview scans exactly the same text this service
        already would, rather than a second copy of this logic.
        """
        return LLMSensitiveDataPolicyService._resolve(value)

    def evaluate(self, value) -> str:
        """The single action to take for `value`: ALLOW, REDACT, or BLOCK.

        Accepts a bare value, an LLMRequest, or an LLMResponse. Every
        data_type Commit #3's LLMSecretRedactionService detects in it is
        looked up against registered policies; the most restrictive
        resulting action wins.
        """
        data_types = {match["pattern"] for match in self._secret_redaction.detect(self._resolve(value))}
        if not data_types:
            return ALLOW

        return max((self._action_for(data_type) for data_type in data_types), key=_ACTION_RANK.__getitem__)

    def allowed(self, value) -> bool:
        """Whether `value` may proceed (as-is, or after redaction) -- i.e. not BLOCK."""
        return self.evaluate(value) != BLOCK

    def applicable_policy_ids(self, value) -> list:
        """policy_id of every registered policy whose data_type was actually
        detected in `value` (Commit #6's audit trail links these).

        A detected data_type with no registered policy contributes
        nothing here -- evaluate()'s own BLOCK-by-default for it is not a
        "policy" that applied, since none was ever registered.
        """
        data_types = {match["pattern"] for match in self._secret_redaction.detect(self._resolve(value))}
        with self._lock:
            return [
                self._policies_by_data_type[data_type].policy_id
                for data_type in data_types
                if data_type in self._policies_by_data_type
            ]
