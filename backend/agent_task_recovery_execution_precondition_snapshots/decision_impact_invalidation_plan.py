from .models import (
    ARTIFACT_STALE,
    ARTIFACT_UNKNOWN,
    INVALIDATION_ACTIONS,
    INVALIDATION_CANCEL,
    INVALIDATION_INVALIDATE,
    INVALIDATION_MANUAL_REVIEW,
    INVALIDATION_REFRESH,
    INVALIDATION_REVALIDATE,
    AgentTaskRecoveryExecutionDecisionImpactInvalidationPlan,
    AgentTaskRecoveryExecutionDecisionImpactInvalidationPlanItem,
)

# Repository rules: artifact kind -> (action, existing mechanism, evidence
# required, kinds it depends on). Listed in dependency order, so plan items
# follow this order. Only kinds with an existing supported mechanism appear.
_RULES = (
    ("authorization", INVALIDATION_REVALIDATE,
     "LLMAgentTaskRecoveryExecutionPreconditionRevalidationService.revalidate() -- resolves the currently "
     "ACTIVE authorization (never fabricates one)",
     ("the stale snapshot's authorization_id", "the task's current active authorization"), ()),
    ("preflight", INVALIDATION_INVALIDATE,
     "LLMAgentTaskRecoveryPreflightInvalidationService.invalidate(task_id, reason)",
     ("the preflight referenced by the stale snapshot", "the decision change that made it stale"),
     ("authorization",)),
    ("execution_snapshot", INVALIDATION_REFRESH,
     "LLMAgentTaskRecoveryExecutionPreconditionRevalidationService.revalidate(task_id, snapshot_id)",
     ("the stale precondition snapshot id", "current authorization and preflight state"),
     ("authorization", "preflight")),
    ("recovery_plan", INVALIDATION_REFRESH,
     "captured afresh by the execution snapshot refresh",
     ("the stale snapshot's recovery plan", "the refreshed snapshot"), ("execution_snapshot",)),
    ("retry_budget", INVALIDATION_CANCEL,
     "LLMAgentTaskRetryScheduler.cancel_retry(task_id) for retries scheduled under the old eligibility; "
     "eligibility is recaptured by the snapshot refresh",
     ("the stale retry eligibility", "any retry scheduled under it"), ("execution_snapshot",)),
    ("readiness", INVALIDATION_REFRESH,
     "captured afresh by the execution snapshot refresh",
     ("the stale readiness result", "the refreshed snapshot"), ("execution_snapshot",)),
    ("execution_pointer", INVALIDATION_REVALIDATE,
     "LLMAgentTaskRecoveryExecutionDecisionFreshnessChainReconciliationService.reconcile(task_id)",
     ("the validated decision chain", "the current pointer"), ()),
    ("reconciliation_result", INVALIDATION_REFRESH,
     "LLMAgentTaskRecoveryExecutionDecisionFreshnessReconciliationLifecycleService.reconcile(task_id) -- "
     "appends a new result; the old one is kept",
     ("the stale reconciliation result", "the reconciled pointer"), ("execution_pointer",)),
    ("lifecycle_result", INVALIDATION_REFRESH,
     "LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionLifecycleService.resolve(task_id) -- "
     "appends a new result; the old one is kept",
     ("the stale lifecycle result", "the current supersession lineage"), ("execution_pointer",)),
)
_RULE_BY_KIND = {rule[0]: rule for rule in _RULES}
_KIND_ORDER = {rule[0]: rank for rank, rule in enumerate(_RULES)}


class InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanError(ValueError):
    """Raised when plan() is given invalid arguments or a staleness result
    for another task."""


class LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService:
    """Turns a staleness result (#2) into a safe, read-only remediation
    plan -- one item for every stale or unknown artifact, so nothing is
    silently discarded. Each supported artifact kind maps to the existing
    service that would refresh, invalidate, revalidate or cancel it
    (preflight invalidation, precondition revalidation, retry cancellation,
    freshness reconciliation, the reconciliation/supersession lifecycles);
    this class runs none of them and adds no invalidation framework.

    An artifact with no supported mechanism, or whose version is unknown,
    becomes manual_review and keeps execution blocked. Items are ordered by
    the dependency order of the rules, so each item's depends_on refers
    only to earlier items.
    """

    def plan(self, task_id: str, staleness_result) -> AgentTaskRecoveryExecutionDecisionImpactInvalidationPlan:
        """Plan remediation for task_id's stale artifacts.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanError:
                If task_id is not a non-empty string, or staleness_result
                is missing or belongs to another task
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanError(
                "task_id is required and must be a non-empty string"
            )
        if staleness_result is None or staleness_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanError(
                "staleness_result does not belong to the task_id given"
            )

        targets = [a for a in staleness_result.artifacts if a.status in (ARTIFACT_STALE, ARTIFACT_UNKNOWN)]
        supported = sorted(
            (a for a in targets if a.status == ARTIFACT_STALE and a.kind in _RULE_BY_KIND),
            key=lambda a: _KIND_ORDER[a.kind],
        )
        manual = [a for a in targets if a not in supported]
        ids = {a.kind: self._artifact_id(a) for a in supported}

        items = []
        for artifact in supported:
            _, action, mechanism, evidence, depends = _RULE_BY_KIND[artifact.kind]
            items.append(
                AgentTaskRecoveryExecutionDecisionImpactInvalidationPlanItem(
                    artifact_id=ids[artifact.kind], artifact_type=artifact.kind, stale_reason=artifact.reason,
                    action=action, mechanism=mechanism, evidence_required=evidence,
                    execution_blocked=artifact.blocking,
                    depends_on=tuple(ids[kind] for kind in depends if kind in ids),
                )
            )
        for artifact in manual:
            reason = (
                "no supported invalidation mechanism exists for this artifact type"
                if artifact.kind not in _RULE_BY_KIND else "the artifact's version could not be established"
            )
            items.append(
                AgentTaskRecoveryExecutionDecisionImpactInvalidationPlanItem(
                    artifact_id=self._artifact_id(artifact), artifact_type=artifact.kind,
                    stale_reason=f"{artifact.reason} ({reason})", action=INVALIDATION_MANUAL_REVIEW,
                    mechanism=None,
                    evidence_required=("the artifact's persisted version reference", "a reviewer's decision"),
                    execution_blocked=True, depends_on=(),
                )
            )

        counts = {action: 0 for action in INVALIDATION_ACTIONS}
        for item in items:
            counts[item.action] += 1
        return AgentTaskRecoveryExecutionDecisionImpactInvalidationPlan(
            task_id=task_id, items=tuple(items), counts_by_action=counts,
            execution_blocked=any(item.execution_blocked for item in items),
        )

    @staticmethod
    def _artifact_id(artifact):
        return f"{artifact.kind}:{artifact.reference}"
