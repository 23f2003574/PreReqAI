from dataclasses import dataclass

ALLOW = "ALLOW"
REDACT = "REDACT"
BLOCK = "BLOCK"
ACTIONS = frozenset({ALLOW, REDACT, BLOCK})


class InvalidSensitiveDataPolicyError(ValueError):
    """Raised when an LLMSensitiveDataPolicy's fields are missing, blank, or invalid."""


@dataclass(frozen=True)
class LLMSensitiveDataPolicy:
    """Immutable declaration of what action applies to one sensitive data_type.

    data_type is one of the categories Commit #3's LLMSecretRedactionService
    already detects (its match "pattern" descriptions -- e.g. "sk- style
    API key", "bearer token", "credential assignment") -- this repo has no
    other established sensitive-data taxonomy (no PII/SSN/etc. categories
    exist anywhere in it), so those already-detected categories are reused
    directly as data_type values rather than inventing a new
    classification scheme.

    The policy is a value object only and performs no evaluation of its
    own -- registering policies and deciding which applies to a given
    value is LLMSensitiveDataPolicyService's job.

    Attributes:
        policy_id: The policy's unique identifier
        data_type: The sensitive-data category this policy governs
        action: What to do when this data_type is detected -- one of
            ALLOW, REDACT, BLOCK
        enabled: Whether this policy currently applies; a disabled policy
            is treated the same as no policy at all -- it never silently
            becomes ALLOW
    """

    policy_id: str
    data_type: str
    action: str
    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.data_type, "data type")

        if self.action not in ACTIONS:
            raise InvalidSensitiveDataPolicyError(
                f"Cannot build a sensitive data policy with an unknown action: {self.action!r}."
            )

        if not isinstance(self.enabled, bool):
            raise InvalidSensitiveDataPolicyError(
                "Cannot build a sensitive data policy with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise InvalidSensitiveDataPolicyError(
                f"Cannot build a sensitive data policy with an empty or blank {field_name}."
            )
