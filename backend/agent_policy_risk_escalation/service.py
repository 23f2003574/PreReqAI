from dataclasses import replace
from datetime import datetime, timedelta, timezone

from backend.agent_policy_risk_approval import (
    APPROVED as APPROVAL_APPROVED,
)
from backend.agent_policy_risk_approval import (
    REQUIRED as APPROVAL_REQUIRED,
)
from backend.agent_policy_risk_approval import (
    LLMAgentRiskApprovalGate,
    UnknownApprovalRequestError,
    effective_status,
)

from .in_memory_store import InMemoryEscalationStore
from .models import (
    APPROVED,
    EXPIRED,
    PENDING,
    REJECTED,
    Escalation,
    new_escalation_id,
)
from .store import EscalationStore

DEFAULT_ESCALATION_WINDOW = timedelta(hours=48)

_OUTCOMES = (APPROVED, REJECTED)


class UnknownEscalationError(KeyError):
    """Raised when get()/resolve() is given an escalation_id that was
    never created."""


class EscalationNotAllowedError(ValueError):
    """Raised when escalate() is attempted against a request_id that is
    not currently REQUIRED (see Rules: "Only review/approval-required
    actions can escalate"), or that already has an active escalation."""


class InvalidEscalationTransitionError(ValueError):
    """Raised when resolve() is attempted on an escalation that is not
    currently PENDING (already decided), or would approve an escalation
    whose original decision carries an explicit policy denial."""


class ExpiredEscalationError(InvalidEscalationTransitionError):
    """Raised when resolve() is attempted on an escalation whose
    resolution window has already lapsed (see Rules: "Expired
    escalations cannot authorize execution")."""


class ScopeMismatchError(ValueError):
    """Raised when resolve() is given a scope_id that does not match
    the escalation's own scope_id (see Rules: "Resolution must be ...
    scope-aware")."""


class LLMAgentRiskEscalationService:
    """Escalates a Commit #5 ApprovalRequirement for human review beyond
    the normal approval gate, and resolves that escalation back through
    the same gate -- not a parallel approval system: this service never
    approves or rejects execution on its own terms. Every real
    authorization transition still happens through Commit #5's own
    LLMAgentRiskApprovalGate.approve()/reject(); resolve() only decides
    *that* an escalation is approved or rejected and then drives the
    one, same gate accordingly (see Rules: "Do not create a parallel
    approval system" / "Reuse existing ... workflow ... where
    available").

    Modeled on backend.session.execution_alert_escalation_service.
    ExecutionAlertEscalationService's own shape (found by inspection):
    composing with an existing service via get(id) rather than
    duplicating its state, rejecting a second active escalation for the
    same underlying record, and an idempotent/terminal resolve() --
    extended with the lazy, time-bound EXPIRED discipline Commit #5's
    own LLMAgentRiskApprovalGate already established for its own
    REQUIRED window (compute is_expired from expires_at at read time,
    never a background job).

    escalate(request_id, reason) only ever escalates a requirement Commit
    #5's own gate reports as REQUIRED right now (see Rules: "Only
    review/approval-required actions can escalate") -- an ALLOW-bypassed
    or DENY-auto-rejected requirement is never REQUIRED in the first
    place, so this is what makes "escalation cannot override an explicit
    policy deny" hold structurally: there is nothing to escalate. As a
    second, independent safety net (mirroring Commit #4/#5's own
    belt-and-suspenders convention), resolve() additionally refuses to
    approve an escalation whose own decision.risk_factors reports a real
    policy_denial, regardless of what state the underlying requirement
    happened to be in when escalate() was called.

    resolve() is actor- and scope-aware: actor is always required and
    non-blank, and an optional scope_id -- when a caller supplies one --
    must match the escalation's own scope_id or resolve() raises
    ScopeMismatchError, rather than silently resolving something outside
    the caller's own scope context.

    Only an InMemory store is provided in this commit, for the same
    reason ApprovalRequirementStore's own docstring already gives (a
    durable Escalation embeds a full RiskDecision, not built for JSON
    round-tripping).
    """

    def __init__(
        self,
        approval_gate: LLMAgentRiskApprovalGate,
        store: EscalationStore = None,
        escalation_window: timedelta = None,
    ):
        self._approval_gate = approval_gate
        self.store = store if store is not None else InMemoryEscalationStore()
        self._escalation_window = escalation_window or DEFAULT_ESCALATION_WINDOW

    def escalate(self, request_id: str, reason: str) -> Escalation:
        """Raise a new PENDING escalation against request_id.

        Raises:
            ValueError: If request_id or reason is missing or blank
            UnknownApprovalRequestError: If request_id was never created
                by Commit #5's own gate
            EscalationNotAllowedError: If the underlying requirement is
                not currently REQUIRED, or it already has an active
                (non-terminal) escalation
        """
        self._require_text(request_id, "request_id")
        self._require_text(reason, "reason")

        requirement = self._approval_gate.get(request_id)
        if requirement.status != APPROVAL_REQUIRED:
            raise EscalationNotAllowedError(
                f"cannot escalate request {request_id!r}: it is {requirement.status}, "
                f"not {APPROVAL_REQUIRED}"
            )

        active_id = self.store.active_for_request(request_id)
        if active_id is not None:
            active = self._effective(self.store.get(active_id))
            if active is not None and active.status not in (EXPIRED,):
                raise EscalationNotAllowedError(
                    f"request {request_id!r} already has an active escalation ({active.escalation_id!r})"
                )

        now = datetime.now(timezone.utc)
        escalation = Escalation(
            escalation_id=new_escalation_id(),
            request_id=request_id,
            scope_id=requirement.scope_id,
            decision=requirement.decision,
            action_context=dict(requirement.action_context),
            reason=reason,
            status=PENDING,
            expires_at=now + self._escalation_window,
            provenance={
                "request_id": request_id,
                "decision": requirement.decision,
                "action_context": dict(requirement.action_context),
            },
        )

        self.store.save(escalation)
        self.store.set_active_for_request(request_id, escalation.escalation_id)
        return escalation

    def resolve(
        self,
        escalation_id: str,
        decision: str,
        actor: str,
        scope_id: str = None,
        resolution_reason: str = None,
    ) -> Escalation:
        """Resolve a still-PENDING, unexpired escalation as APPROVED or
        REJECTED, driving Commit #5's own approval gate accordingly.

        Raises:
            UnknownEscalationError: If escalation_id was never created
            ValueError: If decision is not APPROVED/REJECTED, actor is
                missing or blank, or decision is REJECTED and
                resolution_reason is missing or blank
            ScopeMismatchError: If scope_id is given and does not match
                the escalation's own scope_id
            ExpiredEscalationError: If the escalation's resolution
                window has lapsed
            InvalidEscalationTransitionError: If the escalation is not
                PENDING, or decision is APPROVED but the original
                decision carries an explicit policy denial
        """
        if decision not in _OUTCOMES:
            raise ValueError(f"decision must be one of {_OUTCOMES}, got {decision!r}")
        self._require_text(actor, "actor")
        if decision == REJECTED:
            self._require_text(resolution_reason, "resolution_reason")

        stored = self.store.get(escalation_id)
        if stored is None:
            raise UnknownEscalationError(escalation_id)

        if scope_id is not None and scope_id != stored.scope_id:
            raise ScopeMismatchError(
                f"scope_id {scope_id!r} does not match escalation {escalation_id!r}'s own "
                f"scope {stored.scope_id!r}"
            )

        effective = self._effective(stored)
        if effective.status == EXPIRED:
            raise ExpiredEscalationError(
                f"cannot resolve escalation {escalation_id!r}: its window expired at "
                f"{stored.expires_at!r}"
            )
        if effective.status != PENDING:
            raise InvalidEscalationTransitionError(
                f"cannot resolve escalation {escalation_id!r}: it is {effective.status}, not {PENDING}"
            )

        if decision == APPROVED and bool(stored.decision.risk_factors.get("policy_denial")):
            raise InvalidEscalationTransitionError(
                f"cannot approve escalation {escalation_id!r}: its original decision carries an "
                f"explicit policy denial, which can never be approved into execution"
            )

        # Drive the real authorization transition through Commit #5's
        # own gate first -- if this fails, this escalation's own record
        # stays PENDING rather than diverging from the gate's own state.
        if decision == APPROVED:
            self._approval_gate.approve(stored.request_id, actor)
        else:
            self._approval_gate.reject(stored.request_id, actor, resolution_reason)

        resolved = replace(stored, status=decision, actor=actor, resolved_at=datetime.now(timezone.utc))
        self.store.save(resolved)
        self.store.set_active_for_request(stored.request_id, None)
        return resolved

    def get(self, escalation_id: str) -> Escalation:
        """The escalation's current, effective state -- PENDING reads as
        EXPIRED once its window has lapsed, computed fresh on every
        call (mirrors LLMAgentRiskApprovalGate's own get() discipline).

        Raises:
            UnknownEscalationError: If escalation_id was never created
        """
        stored = self.store.get(escalation_id)
        if stored is None:
            raise UnknownEscalationError(escalation_id)
        return self._effective(stored)

    @staticmethod
    def _effective(escalation, now=None):
        if escalation is None:
            return None

        now = now or datetime.now(timezone.utc)
        new_status = effective_status(escalation.status, escalation.expires_at, PENDING, EXPIRED, now)
        if new_status == escalation.status:
            return escalation
        return replace(escalation, status=new_status)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} is required and must be non-blank")
