import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_policy_risk_decision import RiskDecision

from .expiry import effective_status
from .in_memory_store import InMemoryApprovalRequirementStore
from .models import (
    APPROVED,
    EXPIRED,
    REJECTED,
    REQUIRED,
    SYSTEM_ACTOR,
    ApprovalRequirement,
    new_request_id,
)
from .store import ApprovalRequirementStore

DEFAULT_APPROVAL_WINDOW = timedelta(hours=24)


class UnknownApprovalRequestError(KeyError):
    """Raised when approve()/reject()/get() is given a request_id that
    was never created."""


class InvalidApprovalTransitionError(ValueError):
    """Raised when approve()/reject() is attempted on a requirement that
    is not currently REQUIRED (already decided, or auto-resolved by an
    ALLOW/DENY decision)."""


class ExpiredApprovalError(InvalidApprovalTransitionError):
    """Raised when approve()/reject() is attempted on a requirement whose
    approval window has already lapsed (see Rules: "Reject expired/stale
    approvals")."""


def _context_key(action_context: dict) -> str:
    """A stable identity for "the specific action/context" an
    ApprovalRequirement is scoped to (see Rules: "Approval must be
    scoped to the specific action/context") -- the same
    scope_id/plan_id/step_id/tool_name/arguments shape every action
    boundary in this series already builds action_context from.
    Deterministic and side-effect free: the same action_context always
    produces the same key, so repeated evaluate() calls for an
    unresolved (or already-decided) action reach the same requirement
    rather than minting a new one on every retry.
    """
    try:
        arguments_key = json.dumps(action_context.get("arguments", {}), sort_keys=True, default=str)
    except TypeError:
        arguments_key = repr(action_context.get("arguments"))

    return "|".join(
        str(action_context.get(field))
        for field in ("scope_id", "plan_id", "step_id", "tool_name")
    ) + f"|{arguments_key}"


class LLMAgentRiskApprovalGate:
    """Requires explicit human approval before a Commit #4 REVIEW
    RiskDecision may continue to execution -- not a new authorization
    system: modeled directly on
    backend.session.execution_approval_service.ExecutionApprovalService
    (create a request as pending, decide it exactly once, terminal
    afterward), extended with the one thing that precedent does not
    need: an EXPIRED status for a REQUIRED requirement's own time-bound
    decision window, the same lazy "compute is_expired from expires_at
    at read time, never a background job" discipline
    backend.agent_policy_exceptions.LLMAgentPolicyExceptionService's own
    is_active()/_is_active() already established for this series'
    exception's expires_at.

    evaluate(decision, action_context) is idempotent per action/context
    (see _context_key()) -- calling it again for the same action_context
    while a requirement it already produced is still live (REQUIRED and
    not expired, or already APPROVED/REJECTED) returns that same
    requirement rather than minting a duplicate. This is what makes
    "review actions pause ... until approved" possible at the real
    execution boundary (see LLMAgentRiskGatedExecutionService): a first
    execute_step() call for a REVIEW action creates a pending
    requirement and blocks; once a human approve()s it, a later retry of
    the identical step reaches the same requirement, now APPROVED, and
    is allowed through -- without this gate needing to be told which
    request_id belongs to which retry.

    Rules enforced directly, never left to a caller's discipline:
    - decision.decision == ALLOW always resolves this action/context's
      requirement to APPROVED immediately, actor=SYSTEM_ACTOR (see
      Rules: "allow bypasses approval")
    - decision.decision == DENY always resolves it to REJECTED
      immediately, actor=SYSTEM_ACTOR, and approve()/reject() on that
      request_id afterward always raises InvalidApprovalTransitionError
      -- a human can never approve a real policy/risk denial into
      execution (see Rules: "deny cannot be approved into execution")
    - decision.decision == REVIEW creates (or reuses) a REQUIRED
      requirement with a fixed approval_window deadline; approve()/
      reject() past that deadline raises ExpiredApprovalError, and a
      later evaluate() call for the same action/context mints a fresh
      REQUIRED requirement rather than resurrecting the stale one (see
      Rules: "Reject expired/stale approvals")

    Persists through the same Store/InMemoryStore shape this series has
    used since Commit #1 of the base series (see Rules: "Approval state
    must be persisted using existing infrastructure") -- see
    ApprovalRequirementStore's own docstring for why only an in-memory
    store is provided in this commit.
    """

    def __init__(self, store: ApprovalRequirementStore = None, approval_window: timedelta = None):
        self.store = store if store is not None else InMemoryApprovalRequirementStore()
        self._approval_window = approval_window or DEFAULT_APPROVAL_WINDOW

    def evaluate(self, decision: RiskDecision, action_context: dict) -> ApprovalRequirement:
        """Resolve the ApprovalRequirement for one RiskDecision against
        its action_context -- reusing this action/context's existing
        live requirement when one already exists.

        Raises:
            ValueError: If decision is not a RiskDecision, action_context
                is not a dict, or action_context has no scope_id
        """
        if not isinstance(decision, RiskDecision):
            raise ValueError(f"decision must be a RiskDecision, got {type(decision).__name__}")
        if not isinstance(action_context, dict):
            raise ValueError(f"action_context must be a dict, got {type(action_context).__name__}")

        scope_id = action_context.get("scope_id")
        if not scope_id or not isinstance(scope_id, str):
            raise ValueError("action_context must carry a non-empty scope_id")

        context_key = _context_key(action_context)
        existing_id = self.store.current_for_context(context_key)
        if existing_id is not None:
            effective = self._effective(self.store.get(existing_id))
            if effective is not None and effective.status != EXPIRED:
                return effective
            # else: the prior requirement lapsed unresolved -- fall
            # through and mint a fresh one for this same context, per
            # "Reject expired/stale approvals": a lapsed window is never
            # silently resurrected, but the action still needs a
            # decision, so a new window opens.

        now = datetime.now(timezone.utc)

        if decision.decision == ALLOW:
            requirement = ApprovalRequirement(
                request_id=new_request_id(),
                scope_id=scope_id,
                status=APPROVED,
                decision=decision,
                action_context=dict(action_context),
                actor=SYSTEM_ACTOR,
                resolved_at=now,
            )
        elif decision.decision == DENY:
            requirement = ApprovalRequirement(
                request_id=new_request_id(),
                scope_id=scope_id,
                status=REJECTED,
                decision=decision,
                action_context=dict(action_context),
                actor=SYSTEM_ACTOR,
                reason="policy denies this action; a denial can never be approved into execution",
                resolved_at=now,
            )
        else:
            requirement = ApprovalRequirement(
                request_id=new_request_id(),
                scope_id=scope_id,
                status=REQUIRED,
                decision=decision,
                action_context=dict(action_context),
                expires_at=now + self._approval_window,
            )

        self.store.save(requirement)
        self.store.set_current_for_context(context_key, requirement.request_id)
        return requirement

    def approve(self, request_id: str, actor: str) -> ApprovalRequirement:
        """Approve a still-REQUIRED, unexpired requirement.

        Raises:
            UnknownApprovalRequestError: If request_id was never created
            ValueError: If actor is missing or blank
            ExpiredApprovalError: If the requirement's approval window
                has lapsed
            InvalidApprovalTransitionError: If the requirement is not
                REQUIRED (already decided, or an ALLOW/DENY auto-result)
        """
        return self._decide(request_id, actor, APPROVED, reason=None)

    def reject(self, request_id: str, actor: str, reason: str) -> ApprovalRequirement:
        """Reject a still-REQUIRED, unexpired requirement.

        Raises:
            UnknownApprovalRequestError: If request_id was never created
            ValueError: If actor or reason is missing or blank
            ExpiredApprovalError: If the requirement's approval window
                has lapsed
            InvalidApprovalTransitionError: If the requirement is not
                REQUIRED (already decided, or an ALLOW/DENY auto-result)
        """
        if reason is None or not isinstance(reason, str) or not reason.strip():
            raise ValueError("reason is required and must be non-blank")
        return self._decide(request_id, actor, REJECTED, reason=reason)

    def get(self, request_id: str) -> ApprovalRequirement:
        """The requirement's current, effective state -- REQUIRED reads
        as EXPIRED once its approval window has lapsed, computed fresh
        on every call rather than a persisted mutation (mirrors
        LLMAgentPolicyException's own is_active() discipline).

        Raises:
            UnknownApprovalRequestError: If request_id was never created
        """
        stored = self.store.get(request_id)
        if stored is None:
            raise UnknownApprovalRequestError(request_id)
        return self._effective(stored)

    def _decide(self, request_id: str, actor: str, outcome: str, reason) -> ApprovalRequirement:
        if actor is None or not isinstance(actor, str) or not actor.strip():
            raise ValueError("actor is required and must be non-blank")

        stored = self.store.get(request_id)
        if stored is None:
            raise UnknownApprovalRequestError(request_id)

        effective = self._effective(stored)
        if effective.status == EXPIRED:
            raise ExpiredApprovalError(
                f"cannot decide request {request_id!r}: its approval window expired at "
                f"{stored.expires_at!r}"
            )
        if effective.status != REQUIRED:
            verb = "approve" if outcome == APPROVED else "reject"
            raise InvalidApprovalTransitionError(
                f"cannot {verb} request {request_id!r}: it is {effective.status}, not {REQUIRED}"
            )

        decided = replace(
            stored,
            status=outcome,
            actor=actor,
            reason=reason,
            resolved_at=datetime.now(timezone.utc),
        )
        return self.store.save(decided)

    @staticmethod
    def _effective(requirement, now=None):
        if requirement is None:
            return None

        now = now or datetime.now(timezone.utc)
        new_status = effective_status(requirement.status, requirement.expires_at, REQUIRED, EXPIRED, now)
        if new_status == requirement.status:
            return requirement
        return replace(requirement, status=new_status)
