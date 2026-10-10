from backend.agent_policy_engine import ALLOW, DENY
from backend.agent_policy_risk_approval import APPROVED
from backend.agent_policy_risk_assessment import InvalidActionContextError
from backend.agent_policy_risk_classification import LLMAgentPolicyRiskClassifier
from backend.agent_policy_risk_decision import LLMAgentPolicyRiskDecisionEngine
from backend.agent_policy_risk_review_queue import EXPIRED, RESOLVED, LLMAgentRiskReviewQueue
from backend.agent_policy_risk_thresholds import REVIEW

from .models import RiskGovernanceResult


class LLMAgentRiskGovernanceOrchestrator:
    """The composition root wiring the complete Commit #1-#12 risk-review
    lifecycle into one governance decision -- not a new workflow or
    event framework: evaluate() calls exactly one method from each prior
    commit it needs, in the fixed order the goal's own Flow specifies,
    and never reimplements what any of them already does.

    Every collaborator is passed in already-built, never constructed
    from raw primitives internally -- the same composition-root
    discipline both prior series' own final commits
    (LLMAgentPolicyGovernanceOrchestrator, LLMAgentPolicyDeploymentOrchestrator)
    already established. Only risk_assessor and review_queue are
    required; risk_classifier/decision_engine default to plain
    instances (stateless, nothing to configure); threshold_service and
    execution_service are optional, each degrading exactly the way the
    commit that introduced them already documented (Commit #4's own
    decide() falls back to its own defaults when thresholds is None;
    here, no execution_service simply means evaluate() never executes
    anything, only decides).

    evaluate(action_context) is literally:
        assessment = risk_assessor.assess(action_context)              -- Commit #1
        classification = risk_classifier.classify(assessment)          -- Commit #2
        thresholds = threshold_service.get(scope_id)                   -- Commit #3 (optional)
        decision = decision_engine.decide(action_context, ..., thresholds) -- Commit #4
        -> DENY:   final_decision = DENY
        -> REVIEW: review_item = review_queue.enqueue(decision, action_context) -- Commit #8
                   (itself composing Commits #5/#6 to resolve or create
                   the underlying approval/escalation state -- "resolve
                   existing approval state when applicable" is exactly
                   what Commit #8's own idempotent enqueue() already
                   does: a REVIEW action whose identical action_context
                   was already resolved by a human via Commits #9/#10
                   reaches that same, already-decided ReviewItem here)
                   -> RESOLVED/APPROVED: final_decision = ALLOW
                   -> RESOLVED/REJECTED, or EXPIRED: final_decision = DENY
                   -> still PENDING/CLAIMED: final_decision = REVIEW
        -> ALLOW:  final_decision = ALLOW
        executed = execution_service.execute_step(...) only when
                   final_decision == ALLOW and execution_service was
                   configured -- "enforce final decision" via the real
                   execution boundary, reused exactly as it already
                   behaves (see Rules: "Existing agent behavior remains
                   unchanged when no risk restriction applies" -- an
                   ALLOW just calls through to the same, unmodified
                   execution_service any other caller would use)

    "Explicit policy deny always wins" requires no new check here: a
    real policy denial already forces decision.decision == DENY inside
    Commit #4's own decide() (which itself forces risk_level=CRITICAL
    inside Commit #1's own assess(), and Commit #3's own resolve_action()
    already guarantees CRITICAL always resolves to DENY) -- this
    orchestrator computes decision itself from a real assessment, it
    never receives an externally-supplied, possibly-corrupted RiskDecision
    the way Commit #10's resolver defensively guards against, so there is
    no additional divergence for this layer to guard against on top of
    what Commits #1/#3/#4 already guarantee.

    "review cannot execute without valid approval" / "Expired/rejected
    review blocks execution" hold because executed is only ever produced
    on the ALLOW branch above -- a REVIEW decision whose item is still
    PENDING/CLAIMED, REJECTED, or EXPIRED always resolves final_decision
    to REVIEW or DENY, never ALLOW, so execution_service.execute_step()
    is never even called for it.

    "Learning/analytics/reporting remain outside this execution decision
    path": this orchestrator holds no reference to Commit #11's
    LLMAgentRiskReviewMetrics or Commit #12's
    LLMAgentRiskReviewReportService at all -- not merely "unused", they
    are not even collaborators evaluate() could reach.
    """

    def __init__(
        self,
        risk_assessor,
        review_queue: LLMAgentRiskReviewQueue,
        risk_classifier: LLMAgentPolicyRiskClassifier = None,
        decision_engine: LLMAgentPolicyRiskDecisionEngine = None,
        threshold_service=None,
        execution_service=None,
    ):
        """
        Args:
            risk_assessor: Commit #1's LLMAgentPolicyRiskAssessor
            review_queue: Commit #8's LLMAgentRiskReviewQueue (itself
                composing Commit #5's approval gate and, optionally,
                Commit #6's escalation service)
            risk_classifier: Commit #2's LLMAgentPolicyRiskClassifier,
                defaulting to a plain instance
            decision_engine: Commit #4's LLMAgentPolicyRiskDecisionEngine,
                defaulting to a plain instance
            threshold_service: Optional Commit #3
                LLMAgentPolicyRiskThresholdService, read via
                get(scope_id); None means every scope uses Commit #4's
                own default thresholds
            execution_service: Optional real execution boundary (e.g.
                backend.agent_policy_enforcement.
                LLMAgentPolicyEnforcedExecutionService), used via
                execute_step(plan_id, step_id, subject) only when
                final_decision resolves to ALLOW. None means evaluate()
                never executes anything, only decides
        """
        self._risk_assessor = risk_assessor
        self._review_queue = review_queue
        self._risk_classifier = risk_classifier or LLMAgentPolicyRiskClassifier()
        self._decision_engine = decision_engine or LLMAgentPolicyRiskDecisionEngine()
        self._threshold_service = threshold_service
        self._execution_service = execution_service

    def evaluate(self, action_context: dict) -> RiskGovernanceResult:
        """Assess, classify, threshold, decide, and (for a REVIEW
        decision) resolve one agent action against the existing review
        queue, then enforce the final verdict through the real execution
        boundary when configured and authorized.

        Raises:
            InvalidActionContextError: If action_context is not a dict
                (propagated from Commit #1's own assess())
        """
        if not isinstance(action_context, dict):
            raise InvalidActionContextError(
                f"action_context must be a dict, got {type(action_context).__name__}"
            )

        scope_id = action_context.get("scope_id")

        assessment = self._risk_assessor.assess(action_context)
        classification = self._risk_classifier.classify(assessment)
        thresholds = (
            self._threshold_service.get(scope_id)
            if self._threshold_service is not None and scope_id
            else None
        )
        decision = self._decision_engine.decide(action_context, classification, thresholds)

        reasons = list(decision.reasons)
        review_item = None

        if decision.decision == DENY:
            final_decision = DENY
        elif decision.decision == REVIEW:
            enqueued = self._review_queue.enqueue(decision, action_context)
            # Read back through get() rather than trusting enqueued's own
            # raw return value -- Commit #8's own enqueue() (like Commit
            # #5's evaluate()) returns a freshly-minted item's status
            # as-is without re-checking expiry in the same call, the
            # same lazy-expiry-on-read discipline this whole series has
            # kept since Commit #7; get() is what actually applies it.
            review_item = self._review_queue.get(enqueued.item_id)
            final_decision = self._final_from_review_item(review_item, reasons)
        else:
            final_decision = ALLOW

        executed = None
        if final_decision == ALLOW and self._execution_service is not None:
            executed = self._execute(action_context)

        provenance = {
            "action_context": dict(action_context),
            "assessment": assessment,
            "classification": classification,
            "decision": decision,
            "review_item": review_item,
        }

        return RiskGovernanceResult(
            final_decision=final_decision,
            scope_id=scope_id,
            assessment=assessment,
            classification=classification,
            decision=decision,
            review_item=review_item,
            executed=executed,
            reasons=reasons,
            provenance=provenance,
        )

    @staticmethod
    def _final_from_review_item(item, reasons: list) -> str:
        if item.status == RESOLVED:
            outcome = (item.resolution or {}).get("outcome")
            if outcome == APPROVED:
                return ALLOW
            reasons.append(
                f"review item {item.item_id!r} was rejected: {(item.resolution or {}).get('reason')}"
            )
            return DENY

        if item.status == EXPIRED:
            reasons.append(f"review item {item.item_id!r} expired before resolution")
            return DENY

        reasons.append(f"review item {item.item_id!r} is {item.status}; awaiting resolution")
        return REVIEW

    def _execute(self, action_context: dict):
        plan_id = action_context.get("plan_id")
        step_id = action_context.get("step_id")
        subject = action_context.get("subject")
        return self._execution_service.execute_step(plan_id, step_id, subject)
