from .decision_impact_invalidation import LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationService
from .decision_impact_invalidation_audit import LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService
from .decision_impact_invalidation_lifecycle import (
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService,
)
from .decision_impact_invalidation_plan import LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService
from .decision_impact_invalidation_plan_validation import (
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService,
)
from .decision_impact_invalidation_verification import (
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationService,
)
from .decision_impact_staleness import LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService
from .decision_change_impact import LLMAgentTaskRecoveryExecutionDecisionChangeImpactService


def build_impact_invalidation_lifecycle_service(
    *,
    resolution_service,
    decision_store,
    snapshot_service,
    chain_index_store,
    precondition_revalidation_service=None,
    preflight_invalidation_service=None,
    retry_scheduler=None,
    chain_reconciliation_service=None,
    integrity_service=None,
    **overrides,
) -> LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService:
    """The one place the impact-invalidation lifecycle's collaborators are
    assembled. The caller supplies the external boundaries (the supersession
    resolution service, the decision/snapshot/chain-index stores, and the
    remediation mechanisms); every internal service is built here over those
    same stores, and no service is a module-level singleton, so each call
    returns an independent stack.

    Any collaborator can be replaced with a test double by keyword, using the
    lifecycle constructor's own parameter names (impact_service,
    staleness_service, plan_service, plan_validation_service,
    execution_service, audit_service, verification_service). It holds no
    business logic: it only wires."""
    impact = overrides.pop("impact_service", None) or LLMAgentTaskRecoveryExecutionDecisionChangeImpactService(
        decision_store=decision_store, snapshot_service=snapshot_service,
    )
    staleness = overrides.pop("staleness_service", None) or LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService(
        chain_index_store=chain_index_store,
    )
    planner = overrides.pop("plan_service", None) or LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService()
    validation = overrides.pop("plan_validation_service", None) or (
        LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService(
            impact_service=impact, staleness_service=staleness, plan_service=planner,
            supersession_resolution_service=resolution_service,
        )
    )
    execution = overrides.pop("execution_service", None) or LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationService(
        decision_store=decision_store, impact_service=impact, staleness_service=staleness, plan_service=planner,
        plan_validation_service=validation,
        precondition_revalidation_service=precondition_revalidation_service,
        preflight_invalidation_service=preflight_invalidation_service, retry_scheduler=retry_scheduler,
        chain_reconciliation_service=chain_reconciliation_service,
    )
    audit = overrides.pop("audit_service", None) or LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService()
    verification = overrides.pop("verification_service", None) or (
        LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationService(
            audit_service=audit, decision_store=decision_store, impact_service=impact,
            staleness_service=staleness, snapshot_service=snapshot_service,
            preflight_invalidation_service=preflight_invalidation_service, retry_scheduler=retry_scheduler,
            integrity_service=integrity_service,
        )
    )
    if overrides:
        raise TypeError(f"unknown lifecycle collaborators: {sorted(overrides)}")
    return LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService(
        resolution_service=resolution_service, impact_service=impact, staleness_service=staleness,
        plan_service=planner, plan_validation_service=validation, execution_service=execution,
        audit_service=audit, verification_service=verification,
    )
