from datetime import datetime


def effective_status(
    status: str, expires_at, pending_status: str, expired_status: str, now: datetime
) -> str:
    """Pure, domain-agnostic time-based status resolution: a record
    whose own current status equals pending_status, and whose
    expires_at has passed as of now, reads as expired_status; every
    other status -- already resolved, or not yet due -- is returned
    unchanged.

    Extracted here (rather than kept as a private duplicate in this
    module's own gate.py) so this package's ApprovalRequirement,
    backend.agent_policy_risk_escalation's own Escalation, and Commit
    #7's own LLMAgentRiskExpirationService -- three differently-named
    but structurally identical pending/resolved/expired lifecycles --
    share exactly one implementation of "what does expired mean",
    rather than three independent copies of the same comparison (see
    Commit #7's own Rules: "Expiration must be deterministic from
    stored timestamps"). A status that is not pending_status is
    returned unchanged unconditionally -- this is what makes "already
    resolved decisions must not be rewritten by expiration" hold here,
    at the one place the check is actually made, rather than relying on
    every caller to remember to skip resolved records themselves.

    Pure and side-effect free: never mutates anything, and the same
    (status, expires_at, pending_status, expired_status, now) always
    returns the same result.
    """
    if status != pending_status:
        return status
    if expires_at is not None and expires_at <= now:
        return expired_status
    return status
