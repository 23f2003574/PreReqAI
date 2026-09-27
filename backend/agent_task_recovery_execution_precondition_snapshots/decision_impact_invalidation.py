from .decision_change_impact import LLMAgentTaskRecoveryExecutionDecisionChangeImpactService
from .decision_impact_invalidation_plan import LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService
from .decision_impact_invalidation_plan_validation import (
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService,
)
from .decision_impact_staleness import LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    ARTIFACT_STALE,
    CONFLICT_ACTION_APPLIED,
    CONFLICT_ACTION_FAILED,
    CONFLICT_ACTION_SKIPPED,
    INVALIDATION_MANUAL_REVIEW,
    AgentTaskRecoveryExecutionDecisionImpactInvalidationOutcome,
    AgentTaskRecoveryExecutionDecisionImpactInvalidationResult,
)

_SNAPSHOT_RECAPTURED = ("recovery_plan", "readiness")


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationError(ValueError):
    """Raised when execute() is given an invalid task_id or no plan."""


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationService:
    """Executes a validated impact-invalidation plan (#3/#4) -- the first
    mutation step of analyze -> detect -> plan -> validate -> execute --
    by delegating each action to the repository's existing lifecycle
    service, never to a mutation framework of its own:

      authorization / execution_snapshot / recovery_plan / readiness
          -> LLMAgentTaskRecoveryExecutionPreconditionRevalidationService.revalidate()
             (rebuilds the snapshot only when drift requires it, resolving
             the currently ACTIVE authorization -- never bypassing it)
      preflight          -> LLMAgentTaskRecoveryPreflightInvalidationService.invalidate()
      retry_budget       -> LLMAgentTaskRetryScheduler.cancel_retry()
      execution_pointer  -> LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService.reconcile()
      reconciliation_result -> LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleService.reconcile()
      lifecycle_result   -> LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleService.resolve()

    An unconfigured mechanism fails that item (reported), never guessed.
    Only items that #4 validated are eligible; manual_review items are
    never touched. Immediately before each mutation the artifact is
    re-checked (impact + staleness) and skipped if no longer stale; an
    item runs only once every dependency applied or stopped being stale.
    Each item is its own unit of work -- a failure never hides earlier
    successes. Historical records are preserved: every mechanism above is
    append-only or idempotent. After execution, impact/staleness is
    re-run and still-blocking artifacts are reported.
    """

    def __init__(
        self,
        decision_store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        impact_service: LLMAgentTaskRecoveryExecutionDecisionChangeImpactService = None,
        staleness_service: LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService = None,
        plan_service: LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService = None,
        plan_validation_service: LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService = None,
        precondition_revalidation_service=None,
        preflight_invalidation_service=None,
        retry_scheduler=None,
        chain_reconciliation_service=None,
        reconciliation_lifecycle_service=None,
        supersession_lifecycle_service=None,
    ):
        """All collaborators must share the same stores the plan was built
        from; each mechanism is optional."""
        self._decision_store = decision_store or LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self._impact_service = impact_service or LLMAgentTaskRecoveryExecutionDecisionChangeImpactService(
            decision_store=self._decision_store
        )
        self._staleness_service = staleness_service or LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService()
        self._plan_service = plan_service or LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService()
        self._validation_service = (
            plan_validation_service
            or LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService(
                impact_service=self._impact_service, staleness_service=self._staleness_service,
                plan_service=self._plan_service,
            )
        )
        self._mechanisms = {
            "precondition": precondition_revalidation_service,
            "preflight": preflight_invalidation_service,
            "retry": retry_scheduler,
            "pointer": chain_reconciliation_service,
            "reconciliation": reconciliation_lifecycle_service,
            "lifecycle": supersession_lifecycle_service,
        }

    def execute(self, task_id: str, plan) -> AgentTaskRecoveryExecutionDecisionImpactInvalidationResult:
        """Execute plan's validated, supported actions for task_id.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationError:
                If task_id is not a non-empty string or plan is None
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationError(
                "task_id is required and must be a non-empty string"
            )
        if plan is None:
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationError("plan is required")

        validation = self._validation_service.validate(task_id, plan)
        validated = set(validation.validated_actions)
        applied, skipped, failed = [], [], []
        done = set()  # artifact_ids applied in this run
        snapshot_refreshed = False

        def outcome(item, result, detail):
            return AgentTaskRecoveryExecutionDecisionImpactInvalidationOutcome(
                artifact_id=item.artifact_id, artifact_type=item.artifact_type, action=item.action,
                outcome=result, detail=detail,
            )

        for item in plan.items:
            if item.action == INVALIDATION_MANUAL_REVIEW:
                skipped.append(outcome(item, CONFLICT_ACTION_SKIPPED, "manual_review: left untouched and blocking"))
                continue
            if item.artifact_id not in validated:
                skipped.append(outcome(item, CONFLICT_ACTION_SKIPPED, "not validated against current state"))
                continue
            stale_now = self._stale_ids(task_id, plan)
            if item.artifact_id not in stale_now:
                skipped.append(outcome(item, CONFLICT_ACTION_SKIPPED, "no longer stale; not mutated"))
                continue
            unmet = [d for d in item.depends_on if d not in done and d in stale_now]
            if unmet:
                skipped.append(outcome(item, CONFLICT_ACTION_SKIPPED, f"dependencies not completed: {', '.join(unmet)}"))
                continue
            if item.artifact_type in _SNAPSHOT_RECAPTURED and snapshot_refreshed:
                applied.append(outcome(item, CONFLICT_ACTION_APPLIED, "recaptured by this run's snapshot refresh"))
                done.add(item.artifact_id)
                continue
            try:
                detail = self._run(task_id, item, plan)
            except Exception as error:
                failed.append(outcome(item, CONFLICT_ACTION_FAILED, f"{type(error).__name__}: {error}"))
                continue
            if detail is None:
                failed.append(outcome(item, CONFLICT_ACTION_FAILED, f"no mechanism configured for {item.artifact_type}"))
                continue
            applied.append(outcome(item, CONFLICT_ACTION_APPLIED, detail))
            done.add(item.artifact_id)
            if item.artifact_type in ("execution_snapshot", "authorization"):
                snapshot_refreshed = True

        final_staleness, still_blocking = None, ()
        if plan.previous_decision_id and plan.current_decision_id:
            final_staleness = self._staleness(task_id, plan)
            still_blocking = tuple(
                i.artifact_id for i in self._plan_service.plan(task_id, final_staleness).items if i.execution_blocked
            )
        return AgentTaskRecoveryExecutionDecisionImpactInvalidationResult(
            task_id=task_id, plan_valid=validation.valid, plan_issues=validation.issues, applied=tuple(applied),
            skipped=tuple(skipped), failed=tuple(failed), still_blocking=still_blocking,
            final_staleness=final_staleness,
        )

    def _staleness(self, task_id, plan):
        impact = self._impact_service.analyze(task_id, plan.previous_decision_id, plan.current_decision_id)
        return self._staleness_service.check(task_id, impact)

    def _stale_ids(self, task_id, plan):
        return {
            f"{a.kind}:{a.reference}" for a in self._staleness(task_id, plan).artifacts if a.status == ARTIFACT_STALE
        }

    def _run(self, task_id, item, plan):
        kind = item.artifact_type
        m = self._mechanisms
        if kind in ("authorization", "execution_snapshot") + _SNAPSHOT_RECAPTURED:
            if m["precondition"] is None:
                return None
            previous = self._decision_store.get(plan.previous_decision_id)
            result = m["precondition"].revalidate(task_id, previous.snapshot_id)
            return f"precondition revalidation of snapshot {previous.snapshot_id}: {getattr(result, 'action', result)}"
        if kind == "preflight":
            if m["preflight"] is None:
                return None
            m["preflight"].invalidate(
                task_id, f"execution decision changed from {plan.previous_decision_id} to {plan.current_decision_id}"
            )
            return "preflight invalidated"
        if kind == "retry_budget":
            if m["retry"] is None:
                return None
            m["retry"].cancel_retry(task_id)
            return "retries scheduled under the stale eligibility cancelled"
        if kind == "execution_pointer":
            if m["pointer"] is None:
                return None
            result = m["pointer"].reconcile(task_id)
            if getattr(result, "unresolved", ()):
                raise RuntimeError("reconciliation left unresolved issues: " + "; ".join(result.unresolved))
            return "execution pointer reconciled"
        if kind == "reconciliation_result":
            if m["reconciliation"] is None:
                return None
            return f"reconciliation lifecycle re-run: {getattr(m['reconciliation'].reconcile(task_id), 'status', 'done')}"
        if kind == "lifecycle_result":
            if m["lifecycle"] is None:
                return None
            return f"supersession lifecycle re-run: {getattr(m['lifecycle'].resolve(task_id), 'state', 'done')}"
        return None
