from .failure_classification import LLMAgentTaskEventFailureClassifier
from .models import (
    RECOVERY_POLICY_FEEDBACK_EFFECTIVE,
    RECOVERY_POLICY_FEEDBACK_INEFFECTIVE,
    AgentTaskRecoveryPolicyEffectiveness,
    AgentTaskRecoveryPolicyEffectivenessBreakdown,
)
from .recovery_decision_audit import LLMAgentTaskRecoveryDecisionAuditService
from .recovery_policy_feedback import LLMAgentTaskRecoveryPolicyFeedbackService


class InvalidAgentTaskRecoveryPolicyEffectivenessError(ValueError):
    """Raised when analyze() is given invalid arguments."""


def _empty_breakdown() -> AgentTaskRecoveryPolicyEffectivenessBreakdown:
    return AgentTaskRecoveryPolicyEffectivenessBreakdown(
        decisions_evaluated=0,
        effective_count=0,
        ineffective_count=0,
        unknown_count=0,
        effectiveness_rate=None,
        supporting_decision_ids=(),
        supporting_recovery_ids=(),
    )


class LLMAgentTaskRecoveryPolicyEffectivenessService:
    """Measures whether Commit #8's own recovery recommendations actually
    improve real recovery outcomes -- closing the feedback loop this
    series has been building since Commit #8: recommendation -> decision
    (#9) -> execution (#4/#5) -> outcome comparison (#10) -> policy
    feedback (#11) -> this analysis. Never a second metrics/learning
    framework (Rule: "Do not invent another metrics or learning
    framework"; "Do not duplicate generic analytics infrastructure"):
    analyze() only ever reads Commit #11's own already-recorded
    AgentTaskRecoveryPolicyFeedback records, via
    LLMAgentTaskRecoveryPolicyFeedbackService.list()/list_all() -- it never
    calls plan()/execute()/record() on anything, and never touches
    Commit #10's comparison service directly (every field Commit #10 ever
    computed is already carried through unchanged on Commit #11's own
    feedback record, so re-reading it there is the literal "reuse Commit
    #10 comparison data and Commit #11 feedback" the goal asks for, not a
    second read of the same evidence).

    No existing cross-domain policy/strategy effectiveness pattern was
    reused directly (checked again for this commit, same finding Commit
    #11's own memory already documents): backend.agent_strategy_effectiveness
    is scoped to strategy_id/execution_id, an identity space this series'
    own task_id-scoped recovery domain does not share. This service's own
    shape (a strict effective/ineffective/unknown partition, a rate that
    is None rather than fabricated over zero determined outcomes, a
    per-group breakdown mirroring the overall one) instead mirrors this
    SAME series' own Commit #7 (AgentTaskRecoveryEffectiveness) -- the
    one recovery-effectiveness pattern that actually shares this domain's
    identity space.

    effectiveness_by_policy is keyed by Commit #2's own failure category
    (via an optional failure_classifier collaborator), since no distinct
    policy_id/strategy_id field exists anywhere in this series' own data
    model -- the failure category a recommendation responded to is the
    closest real, already-existing analog to "which policy governed this
    decision." Without a classifier, or for a decision whose own
    failure_event_id cannot be classified, that decision contributes to
    no policy group at all (Rule: "effectiveness by policy/strategy when
    identifiable" -- graceful degradation, the same optional-collaborator
    pattern Commit #7/#8 already establish, never a forced or guessed
    grouping).

    Category lookup deliberately matches against Commit #2's own full raw
    `failures` list (every claimed terminal-state event, event_id-keyed),
    never only its `terminal_failure`: an "effective" decision (Commit
    #10's own was_effective=True) means the task's real, replay-validated
    history never actually ended in terminal FAILED/CANCELLED at all, so
    `terminal_failure` is *always* None for exactly the decisions this
    analysis most wants to categorize -- keying on it alone would silently
    exclude every effective decision from every policy group. Since
    Commit #11's own AgentTaskRecoveryPolicyFeedback does not itself carry
    a failure_event_id, this service reads it back via an
    LLMAgentTaskRecoveryDecisionAuditService lookup (Commit #9's own
    audit already carries it) -- reusing an existing link rather than
    adding yet another additive field to Commit #11's own record for a
    grouping this optional.

    policy_id, when given, filters to decisions whose own failure category
    (via the same classifier) equals it -- and, since that requires a
    classifier to evaluate at all, yields a fully zeroed (not an error)
    result when no classifier was supplied to this service instance:
    "cannot verify any decision belongs to this policy" is treated as "no
    decisions match," never as an error or a guessed match (Rule: "Missing
    evidence stays unknown").

    task_id, when given, filters to that one task's own feedback (Commit
    #11's own list()); omitted, this aggregates
    LLMAgentTaskRecoveryPolicyFeedbackService.list_all() across every
    task -- the only place in this whole series a read is deliberately
    not scoped to one task, since "measure whether recovery-policy
    decisions improve outcomes" is inherently a cross-task question.

    A decision recorded more than once by Commit #11 (its own evidence
    changed between calls, e.g. "no corresponding recovery" superseded
    later by a real outcome) is counted exactly once here, using only its
    most recently recorded feedback -- the same "most informative real
    value already on record" precedent Commit #6's own latest_action
    fallback already establishes, applied here to deduplicating repeated
    evaluations of the very same decision_id rather than to a missing
    field.

    Read-only and deterministic (Rule): every computation here is a pure
    function of Commit #11's own already-deterministic feedback list, with
    no randomness or wall-clock dependency, and this service never writes
    anything -- no policy, feedback, or task state is ever modified here.
    """

    def __init__(
        self,
        feedback_service: LLMAgentTaskRecoveryPolicyFeedbackService = None,
        audit_service: LLMAgentTaskRecoveryDecisionAuditService = None,
        failure_classifier: LLMAgentTaskEventFailureClassifier = None,
    ):
        self._feedback_service = (
            feedback_service if feedback_service is not None else LLMAgentTaskRecoveryPolicyFeedbackService()
        )
        self._audit_service = (
            audit_service if audit_service is not None else LLMAgentTaskRecoveryDecisionAuditService()
        )
        self._failure_classifier = failure_classifier

    def analyze(self, task_id: str = None, policy_id: str = None) -> AgentTaskRecoveryPolicyEffectiveness:
        """Measure recovery-policy effectiveness across task_id's own
        feedback (or across every task, when task_id is omitted),
        optionally narrowed to one identifiable policy (Commit #2's own
        failure category).

        Never raises for a filter that matches nothing: a clean, fully
        zeroed result (every count 0, every rate/group empty) -- this
        service holds no opinion on task or policy identity, the same
        discipline every other read path in this family already
        establishes.

        Raises:
            InvalidAgentTaskRecoveryPolicyEffectivenessError: If task_id
                is given and is not a non-empty string, or policy_id is
                given and is not a non-empty string
        """
        if task_id is not None:
            self._require_text(task_id, "task_id")
        if policy_id is not None:
            self._require_text(policy_id, "policy_id")

        records = self._latest_per_decision(
            self._feedback_service.list(task_id) if task_id is not None else self._feedback_service.list_all()
        )

        category_by_task_and_decision = self._categorize(records) if self._failure_classifier is not None else {}

        if policy_id is not None:
            if self._failure_classifier is None:
                records = []
            else:
                records = [
                    record
                    for record in records
                    if category_by_task_and_decision.get((record.task_id, record.decision_id)) == policy_id
                ]

        overall = self._breakdown(records)

        effectiveness_by_action: dict = {}
        for action in sorted({record.recommended_action for record in records}):
            effectiveness_by_action[action] = self._breakdown(
                [record for record in records if record.recommended_action == action]
            )

        effectiveness_by_policy: dict = {}
        if self._failure_classifier is not None:
            categorized = {
                category_by_task_and_decision[(record.task_id, record.decision_id)]: []
                for record in records
                if (record.task_id, record.decision_id) in category_by_task_and_decision
            }
            for record in records:
                category = category_by_task_and_decision.get((record.task_id, record.decision_id))
                if category is not None:
                    categorized[category].append(record)
            for category in sorted(categorized):
                effectiveness_by_policy[category] = self._breakdown(categorized[category])

        followed = sum(
            1 for r in records if r.executed_action is not None and r.executed_action == r.recommended_action
        )
        changed = sum(
            1 for r in records if r.executed_action is not None and r.executed_action != r.recommended_action
        )

        return AgentTaskRecoveryPolicyEffectiveness(
            task_id=task_id,
            policy_id=policy_id,
            decisions_evaluated=overall.decisions_evaluated,
            recommendations_followed=followed,
            recommendations_changed=changed,
            effective_decisions=overall.effective_count,
            ineffective_decisions=overall.ineffective_count,
            unknown_outcomes=overall.unknown_count,
            effectiveness_rate=overall.effectiveness_rate,
            effectiveness_by_action=effectiveness_by_action,
            effectiveness_by_policy=effectiveness_by_policy,
            supporting_decision_ids=overall.supporting_decision_ids,
            supporting_recovery_ids=overall.supporting_recovery_ids,
        )

    def _categorize(self, records) -> dict:
        """{(task_id, decision_id): failure_category} for every record
        whose own originating failure Commit #2 could classify -- reads
        classify() once per distinct task_id among records, and looks up
        each decision's own failure_event_id via Commit #9's own audit
        (never re-deriving that link a second way).

        Matches against classify()'s full raw `failures` list, keyed by
        event_id, not only its `terminal_failure`: an effective decision's
        own originating failure never became the task's real,
        replay-validated terminal state (that is exactly what "effective"
        means), so terminal_failure alone would silently exclude it."""
        result: dict = {}
        for task_id in {record.task_id for record in records}:
            analysis = self._failure_classifier.classify(task_id)
            category_by_event_id = {failure.event_id: failure.category for failure in analysis.failures}
            for record in records:
                if record.task_id != task_id:
                    continue
                audit = self._audit_service.get(task_id, decision_id=record.decision_id)
                if audit is None or audit.failure_event_id is None:
                    continue
                category = category_by_event_id.get(audit.failure_event_id)
                if category is not None:
                    result[(task_id, record.decision_id)] = category
        return result

    @staticmethod
    def _latest_per_decision(records) -> list:
        latest_by_decision: dict = {}
        for record in records:
            latest_by_decision[record.decision_id] = record
        return list(latest_by_decision.values())

    @staticmethod
    def _breakdown(records) -> AgentTaskRecoveryPolicyEffectivenessBreakdown:
        if not records:
            return _empty_breakdown()

        effective = [r for r in records if r.effectiveness == RECOVERY_POLICY_FEEDBACK_EFFECTIVE]
        ineffective = [r for r in records if r.effectiveness == RECOVERY_POLICY_FEEDBACK_INEFFECTIVE]
        determined = len(effective) + len(ineffective)

        return AgentTaskRecoveryPolicyEffectivenessBreakdown(
            decisions_evaluated=len(records),
            effective_count=len(effective),
            ineffective_count=len(ineffective),
            unknown_count=len(records) - determined,
            effectiveness_rate=(len(effective) / determined) if determined > 0 else None,
            supporting_decision_ids=tuple(record.decision_id for record in records),
            supporting_recovery_ids=tuple(record.recovery_id for record in records if record.recovery_id is not None),
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPolicyEffectivenessError(
                f"{field_name} must be a non-empty string when given"
            )
