from datetime import datetime
from typing import Union


def effective_status(
    status: str, expires_at, pending_status: Union[str, tuple, frozenset, set], expired_status: str, now: datetime
) -> str:
    """Pure, domain-agnostic time-based status resolution: a record
    whose own current status is one of pending_status, and whose
    expires_at has passed as of now, reads as expired_status; every
    other status -- already resolved, or not yet due -- is returned
    unchanged.

    Extracted here (rather than kept as a private duplicate in this
    module's own gate.py) so this package's ApprovalRequirement,
    backend.agent_policy_risk_escalation's own Escalation, Commit #7's
    own LLMAgentRiskExpirationService, and Commit #8's own
    LLMAgentRiskReviewQueue -- four differently-shaped but structurally
    identical pending/resolved/expired lifecycles -- share exactly one
    implementation of "what does expired mean", rather than four
    independent copies of the same comparison (see Commit #7's own
    Rules: "Expiration must be deterministic from stored timestamps").
    A status that is not in pending_status is returned unchanged
    unconditionally -- this is what makes "already resolved decisions
    must not be rewritten by expiration" hold here, at the one place
    the check is actually made, rather than relying on every caller to
    remember to skip resolved records themselves.

    pending_status accepts either a single status string (Commit #5/#6's
    own two-non-terminal-value-less lifecycles: exactly one status
    means "still open") or a tuple/set of them (Commit #8's own
    PENDING-or-CLAIMED lifecycle, where either one can still lapse) --
    broadened for Commit #8's own reuse without changing behavior for
    any existing single-string caller.

    Pure and side-effect free: never mutates anything, and the same
    (status, expires_at, pending_status, expired_status, now) always
    returns the same result.
    """
    pending_statuses = {pending_status} if isinstance(pending_status, str) else set(pending_status)

    if status not in pending_statuses:
        return status
    if expires_at is not None and expires_at <= now:
        return expired_status
    return status
