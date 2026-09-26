from .decision_freshness_chain_reconciliation import (
    LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService,
)
from .decision_supersession_conflict_plan import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService,
)
from .decision_supersession_conflict_plan_validation import (
    LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService,
)
from .decision_supersession_validation import LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService
from .models import (
    CONFLICT_ACTION_APPLIED,
    CONFLICT_ACTION_DELEGATED,
    CONFLICT_ACTION_FAILED,
    CONFLICT_ACTION_SKIPPED,
    PLAN_REPAIRABLE_METADATA,
    PLAN_REQUIRES_REVALIDATION,
    AgentTaskRecoveryExecutionDecisionSupersessionConflictActionOutcome,
    AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionResult,
)


class InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionError(ValueError):
    """Raised when execute() is given an invalid task_id or no plan."""


class LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionService:
    """Executes only the validated, mechanically safe items of a conflict
    resolution plan (#6), after #7 re-validates the plan against current
    evidence -- the first mutating step of detect -> report -> plan ->
    validate -> execute, built on existing services rather than another
    repair framework:

      * repairable_metadata (a stale pointer on the validated lineage) is
        applied by the existing freshness-chain reconciliation service,
        which only ever moves the pointer to the validated terminal and
        copies its verdict -- never rewriting a decision, manufacturing
        lineage, or turning review/block into allow;
      * requires_revalidation is delegated to the existing freshness
        revalidation service for the predecessor decision; the conflict
        stays blocking until a reviewer settles it;
      * requires_manual_review and unresolvable items are never touched.

    Each item is re-checked against a freshly rebuilt plan immediately
    before it runs. The package has no transaction/rollback mechanism, so
    each item is its own unit of work: a failure is reported and never
    undoes an earlier successful item. The supersession chain is
    re-validated (#2) after every mutation batch. Idempotent: once an item
    has been applied its conflict no longer exists, so a repeated run
    skips it.
    """

    def __init__(
        self,
        plan_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService = None,
        plan_validation_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService = None,
        reconciliation_service: LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService = None,
        revalidation_service=None,
        supersession_validation_service: LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService = None,
    ):
        """All collaborators must share the same stores. revalidation_service
        is the existing LLMAgentTaskRecoveryExecutionDecisionFreshnessRevalidationService
        (wired to the real snapshot/authorization stack); without one,
        requires_revalidation items are reported failed."""
        self._plan_service = (
            plan_service if plan_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanService()
        )
        self._plan_validation_service = (
            plan_validation_service if plan_validation_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionPlanValidationService(
                plan_service=self._plan_service
            )
        )
        self._reconciliation_service = (
            reconciliation_service if reconciliation_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService()
        )
        self._revalidation_service = revalidation_service
        self._supersession_validation_service = (
            supersession_validation_service if supersession_validation_service is not None
            else LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService()
        )

    def execute(self, task_id: str, plan) -> AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionResult:
        """Execute plan's safe items for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionError:
                If task_id is not a non-empty string or plan is None
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionError(
                "task_id is required and must be a non-empty string"
            )
        if plan is None:
            raise InvalidAgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionError("plan is required")

        validation = self._plan_validation_service.validate(task_id, plan)
        validated = set(validation.validated_conflicts)
        applied, skipped, failed, batches = [], [], [], []

        def outcome(item, result, detail):
            return AgentTaskRecoveryExecutionDecisionSupersessionConflictActionOutcome(
                conflict_id=item.conflict_id, conflict_type=item.conflict_type,
                classification=item.classification, outcome=result, detail=detail,
            )

        repairs, revalidations, seen = [], [], set()
        for item in plan.items:
            if item.conflict_id in seen:
                continue
            seen.add(item.conflict_id)
            if item.conflict_id not in validated:
                skipped.append(outcome(item, CONFLICT_ACTION_SKIPPED, "not validated against current evidence"))
            elif item.classification == PLAN_REPAIRABLE_METADATA:
                repairs.append(item)
            elif item.classification == PLAN_REQUIRES_REVALIDATION:
                revalidations.append(item)
            else:
                skipped.append(outcome(item, CONFLICT_ACTION_SKIPPED, f"{item.classification}: left untouched and blocking"))

        for batch, run in ((repairs, self._repair), (revalidations, self._revalidate)):
            if not batch:
                continue
            mutated = False
            for item in batch:
                current = {i.conflict_id: i for i in self._plan_service.plan(task_id).items}.get(item.conflict_id)
                if current is None or current.classification != item.classification:
                    skipped.append(outcome(item, CONFLICT_ACTION_SKIPPED, "no longer applicable to current evidence"))
                    continue
                try:
                    result, detail = run(task_id, item)
                except Exception as error:
                    failed.append(outcome(item, CONFLICT_ACTION_FAILED, f"{type(error).__name__}: {error}"))
                    continue
                mutated = True
                (failed if result == CONFLICT_ACTION_FAILED else applied).append(outcome(item, result, detail))
            if mutated:
                batches.append(self._supersession_validation_service.validate(task_id))

        remaining = self._plan_service.plan(task_id)
        return AgentTaskRecoveryExecutionDecisionSupersessionConflictResolutionResult(
            task_id=task_id, plan_valid=validation.valid, plan_issues=validation.issues,
            applied=tuple(applied), skipped=tuple(skipped), failed=tuple(failed),
            still_blocking=tuple(item.conflict_id for item in remaining.items if item.execution_blocked),
            batch_validations=tuple(batches),
            final_validation=batches[-1] if batches else self._supersession_validation_service.validate(task_id),
        )

    def _repair(self, task_id, item):
        reconciliation = self._reconciliation_service.reconcile(task_id)
        if reconciliation.changes and not reconciliation.unresolved:
            return CONFLICT_ACTION_APPLIED, "; ".join(reconciliation.changes)
        return CONFLICT_ACTION_FAILED, "reconciliation did not move the pointer: " + (
            "; ".join(reconciliation.unresolved) or "no change was needed"
        )

    def _revalidate(self, task_id, item):
        if self._revalidation_service is None:
            return CONFLICT_ACTION_FAILED, "no freshness revalidation service is configured"
        result = self._revalidation_service.revalidate(task_id, item.decision_ids[0])
        return CONFLICT_ACTION_DELEGATED, (
            f"freshness revalidation of {item.decision_ids[0]}: {result.action}"
            + (f" -> {result.new_decision_id}" if getattr(result, "new_decision_id", None) else "")
            + "; the conflict stays blocking until reviewed"
        )
