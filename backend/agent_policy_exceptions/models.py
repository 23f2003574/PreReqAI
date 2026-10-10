from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

# Exception lifecycle. Mirrors the shape
# backend.session.execution_policy_risk_override.ExecutionPolicyRiskOverride
# already uses for the repo's other explicit, time-bound tolerance (an
# `enabled` bool there) -- expressed here as a closed status vocabulary
# instead, the same ACTIVE/ARCHIVED-shaped convention
# backend.agent_policy_engine already established for this series, so a
# revoked exception's record (and its reason) is retained exactly like a
# revoked override's is, never deleted.
ACTIVE = "active"
REVOKED = "revoked"
STATUSES = frozenset({ACTIVE, REVOKED})


class InvalidPolicyExceptionError(ValueError):
    """Raised when an LLMAgentPolicyException's fields are missing, blank, or invalid."""


@dataclass(frozen=True)
class LLMAgentPolicyException:
    """Immutable record of an explicitly granted, time-bound, narrowly
    scoped relief from one specific Commit #1 policy's denial.

    Modeled directly on
    backend.session.execution_policy_risk_override.ExecutionPolicyRiskOverride:
    a value object only, performing no evaluation of its own -- creating,
    listing active, and revoking exceptions is
    LLMAgentPolicyExceptionService's job, and deciding whether one
    actually changes an action's outcome is
    LLMAgentPolicyExceptionAwareDecisionEngine's. Never mutates or
    replaces the LLMAgentPolicy it names; policy_id is a reference, and
    the underlying policy's own rules are untouched by any exception
    that exists against it.

    Attributes:
        scope_id: The scope this exception applies within. An exception
            can never be consulted for, or leak into, any other scope
        policy_id: The specific Commit #1 LLMAgentPolicy this exception
            grants relief from -- an exception excepts one named policy's
            denial, never "any" or "all" policy in the scope
        match: The action/resource constraint this exception is narrowed
            to, in the same {field: expected} shape
            backend.agent_policy_engine.LLMAgentPolicyRule.match already
            uses (expected may be a single value or a list/tuple of
            acceptable values). Required and non-empty: a blanket
            exception with no constraint at all is never allowed to
            exist, so an exception can only ever be as broad as the
            fields it actually names -- "narrow ... preferred over broad
            overrides" is enforced here, not left as a convention to
            follow
        reason: Why this exception was granted. Required, and retained
            for as long as the exception's record exists, including
            after it expires or is revoked
        expires_at: When this exception stops applying. Required: an
            exception with no expiry can never be created
        status: ACTIVE or REVOKED. A revoked exception is inactive
            immediately, even before expires_at
    """

    scope_id: str
    policy_id: str
    match: dict
    reason: str
    expires_at: datetime
    status: str = ACTIVE
    exception_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.scope_id, "scope ID")
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.reason, "reason")

        if not isinstance(self.match, dict) or not self.match:
            raise InvalidPolicyExceptionError(
                "Cannot build an agent policy exception with an empty or non-dict match: "
                "an exception must be narrowed to a specific action/resource constraint."
            )
        for key in self.match:
            if not isinstance(key, str) or not key.strip():
                raise InvalidPolicyExceptionError(
                    "Cannot build an agent policy exception with an empty or non-string match key."
                )

        if not isinstance(self.expires_at, datetime):
            raise InvalidPolicyExceptionError(
                "Cannot build an agent policy exception with no expires_at."
            )

        if self.status not in STATUSES:
            raise InvalidPolicyExceptionError(
                f"status {self.status!r} is not one of {sorted(STATUSES)}"
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise InvalidPolicyExceptionError(
                f"Cannot build an agent policy exception with an empty or blank {field_name}."
            )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["expires_at"] = self.expires_at.isoformat()
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentPolicyException":
        payload = dict(data)
        for key in ("expires_at", "created_at"):
            value = payload.get(key)
            if isinstance(value, str):
                payload[key] = datetime.fromisoformat(value)
        return cls(**payload)
