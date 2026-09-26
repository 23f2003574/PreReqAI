import hashlib

from .decision_supersession_conflict import LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService
from .decision_supersession_resolution import LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService
from .models import (
    PLAN_CLASSIFICATIONS,
    PLAN_REPAIRABLE_METADATA,
    PLAN_REQUIRES_MANUAL_REVIEW,
    PLAN_REQUIRES_REVALIDATION,
    PLAN_UNRESOLVABLE,
    RESOLUTION_RESOLVED,
    SUPERSESSION_CONFLICT_CROSS_TASK,
    SUPERSESSION_CONFLICT_CYCLE,
    SUPERSESSION_CONFLICT_FRESHNESS_DISAGREEMENT,
    SUPERSESSION_CONFLICT_INVALID_REASON,
    SUPERSESSION_CONFLICT_MISSING_DECISION,
    SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS,
    SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT,
    SUPERSESSION_CONFLICT_SUCCESSOR_NOT_NEWER,
    AgentTaskRecoveryExecutionDecisionSupersessionConflictPlanItem,
    AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlan,
)

_FRESHNESS = "freshness_revalidation"
_RECONCILIATION = "freshness_reconciliation"
_RECONCILE_ACTION = (
    "run LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService.reconcile() to advance the "
    "stale current pointer along the validated lineage"
)

# conflict type -> (classification, proposed safe action, evidence required, depends_on)
_RULES = {
    SUPERSESSION_CONFLICT_CYCLE: (
        PLAN_UNRESOLVABLE,
        "keep execution blocked; the append-only lineage contains a cycle that no automated step can undo -- "
        "escalate for manual investigation",
        ("the supersession records forming the cycle", "the persisted decisions' creation times"),
        (),
    ),
    SUPERSESSION_CONFLICT_MULTIPLE_SUCCESSORS: (
        PLAN_REQUIRES_MANUAL_REVIEW,
        "keep execution blocked; a reviewer must decide which successor, if any, is authoritative -- no "
        "successor is selected automatically",
        ("every competing supersession record", "each successor decision's verdict and evidence"),
        (_FRESHNESS,),
    ),
    SUPERSESSION_CONFLICT_CROSS_TASK: (
        PLAN_UNRESOLVABLE,
        "keep execution blocked; a link to another task's decision can never be valid lineage for this task",
        ("the supersession record", "the linked decision's owning task"),
        (),
    ),
    SUPERSESSION_CONFLICT_MISSING_DECISION: (
        PLAN_UNRESOLVABLE,
        "keep execution blocked; the referenced decision cannot be recovered or manufactured",
        ("the supersession record", "the decision store's record of the missing decision id"),
        (),
    ),
    SUPERSESSION_CONFLICT_SUCCESSOR_NOT_NEWER: (
        PLAN_REQUIRES_MANUAL_REVIEW,
        "keep execution blocked; a reviewer must confirm whether the link or the decision timestamps are wrong",
        ("the supersession record", "both decisions' creation times"),
        (),
    ),
    SUPERSESSION_CONFLICT_FRESHNESS_DISAGREEMENT: (
        PLAN_REQUIRES_REVALIDATION,
        "keep execution blocked; run LLMAgentTaskRecoveryExecutionDecisionFreshnessRevalidationService.revalidate() "
        "for the predecessor and review which successor the fresh evidence supports",
        ("the freshness audit record", "the conflicting supersession record", "current precondition evidence"),
        (_FRESHNESS, _RECONCILIATION),
    ),
    SUPERSESSION_CONFLICT_INVALID_REASON: (
        PLAN_REQUIRES_MANUAL_REVIEW,
        "keep execution blocked; a reviewer must supply and confirm the supersession reason",
        ("the supersession record", "the revalidation or approval that justified the replacement"),
        (),
    ),
}


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanError(ValueError):
    """Raised when plan() is given an invalid task_id."""


class LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService:
    """Produces an explicit, read-only plan for resolving the lineage
    conflicts detected by #4 -- detect -> report -> plan, with no mutation
    in the planning layer: every item is built from the detector's own
    conflicts and the supersession resolution (#3); nothing is resolved,
    repaired or revalidated here, and no winning decision is ever chosen.

    Only a stale reconciliation pointer that already lies on the validated
    lineage is classified repairable_metadata (the existing reconciliation
    service would advance it); everything ambiguous goes to revalidation or
    manual review, and records that can never become valid lineage are
    unresolvable. Every item keeps execution blocked -- the conflict is
    still present when the plan is made. Items are ordered as the detector
    orders conflicts.
    """

    def __init__(
        self,
        conflict_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService = None,
        resolution_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService = None,
    ):
        if conflict_service is None:
            resolution_service = (
                resolution_service if resolution_service is not None
                else LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService()
            )
            conflict_service = LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictService(
                resolution_service=resolution_service
            )
        self._conflict_service = conflict_service
        self._resolution_service = (
            resolution_service if resolution_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService()
        )

    def plan(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlan:
        """task_id's conflict resolution plan.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanError(
                "task_id is required and must be a non-empty string"
            )

        detection = self._conflict_service.detect(task_id)
        resolution = self._resolution_service.resolve(task_id)
        items = tuple(self._item(conflict, resolution) for conflict in detection.conflicts)
        counts = {classification: 0 for classification in PLAN_CLASSIFICATIONS}
        for item in items:
            counts[item.classification] += 1
        return AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlan(
            task_id=task_id, items=items, counts_by_classification=counts,
            execution_blocked=bool(items) or resolution.resolution_state != RESOLUTION_RESOLVED,
            resolution_state=resolution.resolution_state,
        )

    @staticmethod
    def _item(conflict, resolution):
        if conflict.conflict_type == SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT:
            if resolution.reconciled_pointer in resolution.chain[:-1]:
                rule = (
                    PLAN_REPAIRABLE_METADATA, _RECONCILE_ACTION,
                    ("the validated supersession lineage", "the current reconciliation pointer"),
                    (_RECONCILIATION,),
                )
            else:
                rule = (
                    PLAN_REQUIRES_MANUAL_REVIEW,
                    "keep execution blocked; the current pointer names a decision outside the validated lineage -- "
                    "a reviewer must decide which is authoritative",
                    ("the current reconciliation pointer", "the validated supersession lineage"),
                    (_RECONCILIATION,),
                )
        else:
            rule = _RULES.get(conflict.conflict_type) or (
                PLAN_REQUIRES_MANUAL_REVIEW, "keep execution blocked; unrecognised conflict type needs review",
                ("the conflict's evidence records",), (),
            )
        classification, action, evidence_required, depends_on = rule
        digest = hashlib.sha1(
            repr((conflict.conflict_type, conflict.decision_ids, conflict.evidence_ids)).encode()
        ).hexdigest()[:12]
        return AgentTaskRecoveryExecutionDecisionSupersessionConflictPlanItem(
            conflict_id=f"{conflict.conflict_type}:{digest}", conflict_type=conflict.conflict_type,
            classification=classification, decision_ids=conflict.decision_ids,
            evidence_ids=conflict.evidence_ids, proposed_action=action, evidence_required=evidence_required,
            execution_blocked=True, depends_on=depends_on, detail=conflict.detail,
        )
