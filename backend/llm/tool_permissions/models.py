from dataclasses import dataclass, field
from typing import Optional

# Authorization outcome vocabulary, reusing the classification the repo
# already uses for execution authorization
# (ResearchWorkspaceConsumerProjectionExecutionAuthorization: authorized /
# conditional / denied) rather than introducing a second set of names.
AUTHORIZED = "AUTHORIZED"
CONDITIONAL = "CONDITIONAL"
DENIED = "DENIED"
DECISIONS = frozenset({AUTHORIZED, CONDITIONAL, DENIED})

# A policy whose subject is ANY_SUBJECT applies to every caller -- the
# scope-wide default a per-subject policy narrows.
ANY_SUBJECT = "*"


class InvalidToolPolicyError(ValueError):
    """Raised when a policy's fields are missing, blank, or the wrong type."""


@dataclass(frozen=True)
class LLMToolPermissionPolicy:
    """Immutable declaration of whether one subject may invoke one tool.

    Modeled on the repo's existing allow/deny policy value objects
    (ExecutionNetworkTrafficPolicy, ExecutionSecretTrustPolicy): the policy
    is a value object only and performs no authorization of its own.
    Registering, revoking, and evaluating policies is the responsibility of
    LLMToolPermissionService, which never mutates a registered policy.

    Attributes:
        policy_id: The policy's unique identifier
        tool_name: The registered tool this policy governs
        subject: Who the policy applies to -- a user, a role, or any other
            scope identifier the caller uses. ANY_SUBJECT ("*") makes it a
            tool-wide default that a per-subject policy narrows
        allowed: Whether this subject may invoke the tool. False is an
            explicit deny, which always beats any allow
        conditions: Argument constraints that must hold for this policy to
            apply at all, as {argument_name: expected}, where expected is a
            single value or a list/tuple of acceptable values. Empty means
            the policy applies unconditionally
    """

    policy_id: str
    tool_name: str
    subject: str
    allowed: bool
    conditions: dict = field(default_factory=dict)

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.tool_name, "tool name")
        self._require_text(self.subject, "subject")

        if not isinstance(self.allowed, bool):
            raise InvalidToolPolicyError(
                "Cannot build a tool permission policy with a non-boolean allowed."
            )

        if not isinstance(self.conditions, dict):
            raise InvalidToolPolicyError(
                "Cannot build a tool permission policy with non-dict conditions."
            )

        for key in self.conditions:
            if not isinstance(key, str) or not key.strip():
                raise InvalidToolPolicyError(
                    "Cannot build a tool permission policy with an empty or "
                    "non-string condition key."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise InvalidToolPolicyError(
                f"Cannot build a tool permission policy with an empty or blank {field_name}."
            )


@dataclass(frozen=True)
class LLMToolAuthorization:
    """Immutable outcome of one authorization check against a tool call.

    Mirrors the repo's existing authorization result shape
    (ArtifactAccessResult: allowed + reason), carrying in addition the
    repo's authorized/conditional/denied classification and which policy
    decided, so a denial can always be traced to the policy that caused it.
    decision is CONDITIONAL when the policy that allowed the call carried
    conditions that were checked and held; policy_id is None when no policy
    applied at all.
    """

    allowed: bool
    decision: str
    reason: str
    policy_id: Optional[str] = None
