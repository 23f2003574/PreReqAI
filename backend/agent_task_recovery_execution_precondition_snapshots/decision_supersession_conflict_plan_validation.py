from .decision_freshness_audit import LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .decision_supersession import InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore
from .decision_supersession_conflict_plan import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService,
)
from .models import (
    PLAN_CLASSIFICATIONS,
    PLAN_REPAIRABLE_METADATA,
    PLAN_REQUIRES_MANUAL_REVIEW,
    PLAN_UNRESOLVABLE,
    PLAN_VALIDATION_INVALID,
    PLAN_VALIDATION_VALID,
    SUPERSESSION_CONFLICT_CROSS_TASK,
    SUPERSESSION_CONFLICT_MISSING_DECISION,
    SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT,
    AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationResult,
)

# Plan fields that must equal what current evidence produces for the same conflict.
_MATCHED_FIELDS = (
    "conflict_type", "classification", "decision_ids", "evidence_ids", "proposed_action",
    "evidence_required", "depends_on",
)


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationError(ValueError):
    """Raised when validate() is given an invalid task_id or no plan."""


class LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService:
    """Validates a conflict-resolution plan (#6) against CURRENT persisted
    evidence before anything consumes it -- it never trusts the old plan
    blindly and never executes repair or revalidation. The current plan is
    rebuilt through the #6 planning service itself (which re-runs #4
    detection and #3/#2 lineage resolution) -- no second planner -- and
    the given plan is compared with it item by item; evidence ids and
    decision ownership are re-checked against the supersession records,
    freshness audit trail and decision store.

    Fails closed: any stale, missing, duplicated or altered item, any
    non-blocking item, or any repair action other than advancing a pointer
    along the validated lineage makes the plan INVALID. Read-only and
    deterministic.
    """

    def __init__(
        self,
        plan_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService = None,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        supersession_store=None,
        freshness_audit_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService = None,
    ):
        """Pass a plan_service wired to the same decision_store/
        supersession_store/freshness_audit_service."""
        self._plan_service = (
            plan_service if plan_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService()
        )
        self._decision_store = (
            decision_store if decision_store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        )
        self._supersession_store = (
            supersession_store if supersession_store is not None
            else InMemoryAgentTaskRecoveryExecutionDecisionSupersessionStore()
        )
        self._audit_service = (
            freshness_audit_service if freshness_audit_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessAuditService()
        )

    def validate(
        self, task_id: str, plan
    ) -> AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationResult:
        """Validate plan for task_id against current persisted evidence.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationError:
                If task_id is not a non-empty string or plan is None
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationError(
                "task_id is required and must be a non-empty string"
            )
        if plan is None:
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationError(
                "plan is required"
            )

        issues = []
        if plan.task_id != task_id:
            issues.append(f"the plan was made for task {plan.task_id!r}, not {task_id!r}")

        current = self._plan_service.plan(task_id)
        current_items = {item.conflict_id: item for item in current.items}
        known_evidence = {record.supersession_id for record in self._supersession_store.list_for_task(task_id)} | {
            audit.audit_id for audit in self._audit_service.list(task_id)
        }

        seen, validated = {}, []
        for item in plan.items:
            cid = item.conflict_id
            if cid in seen:
                issues.append(
                    f"conflict {cid} is planned more than once"
                    + ("" if seen[cid] == item else " with conflicting actions")
                )
                continue
            seen[cid] = item
            item_issues = []

            if item.classification not in PLAN_CLASSIFICATIONS:
                item_issues.append(f"conflict {cid} has unknown classification {item.classification!r}")
            if item.classification == PLAN_REPAIRABLE_METADATA and (
                item.conflict_type != SUPERSESSION_CONFLICT_POINTER_DISAGREEMENT
            ):
                item_issues.append(
                    f"conflict {cid} plans a metadata repair for a {item.conflict_type} conflict, which could "
                    "silently change the authoritative decision"
                )
            if not item.execution_blocked:
                label = (
                    f"{item.classification} " if item.classification in (
                        PLAN_REQUIRES_MANUAL_REVIEW, PLAN_UNRESOLVABLE,
                    ) else ""
                )
                item_issues.append(f"{label}conflict {cid} does not keep execution blocked")
            if not item.evidence_required:
                item_issues.append(f"conflict {cid} names no required evidence")
            for evidence_id in item.evidence_ids:
                if evidence_id not in known_evidence:
                    item_issues.append(f"conflict {cid} cites evidence {evidence_id}, which is not persisted")
            if item.conflict_type not in (SUPERSESSION_CONFLICT_MISSING_DECISION, SUPERSESSION_CONFLICT_CROSS_TASK):
                for decision_id in item.decision_ids:
                    decision = self._decision_store.get(decision_id)
                    if decision is None or decision.task_id != task_id:
                        item_issues.append(f"conflict {cid} affects decision {decision_id}, which is not this task's")

            now = current_items.get(cid)
            if now is None:
                item_issues.append(f"conflict {cid} no longer exists (already resolved or stale plan)")
            else:
                for field_name in _MATCHED_FIELDS:
                    if getattr(item, field_name) != getattr(now, field_name):
                        item_issues.append(
                            f"conflict {cid}: planned {field_name} does not match what current evidence requires"
                        )

            issues.extend(item_issues)
            if not item_issues:
                validated.append(cid)

        for cid in current_items:
            if cid not in seen:
                issues.append(f"current conflict {cid} is missing from the plan")
        if plan.resolution_state != current.resolution_state:
            issues.append(
                f"the plan assumed lineage state {plan.resolution_state!r}, but it is now {current.resolution_state!r}"
            )
        if current.execution_blocked and not plan.execution_blocked:
            issues.append("the plan unblocks execution while the current lineage still requires it to be blocked")

        return AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationResult(
            task_id=task_id, status=PLAN_VALIDATION_INVALID if issues else PLAN_VALIDATION_VALID,
            issues=tuple(issues), validated_conflicts=tuple(validated),
            blocking_conflicts=tuple(item.conflict_id for item in current.items if item.execution_blocked),
        )
