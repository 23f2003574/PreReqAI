"""Wiring of the recovery execution decision lifecycle services. Shared by the
HTTP API (backend/api/recovery_decision_routes.py) and the CLI (backend/cli.py,
which re-exports these builders), so serving the API never imports the CLI."""

from types import SimpleNamespace

from backend.agent_task_recovery_execution_precondition_snapshots import (
    LLMAgentTaskRecoveryExecutionDecisionChangeImpactService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationService,
    LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService,
    LLMAgentTaskRecoveryExecutionDecisionLifecycleReadinessService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
)


def _build_collaborators(decision_store=None):
    """Wire the #1-#10 services this package's facade (#1) and health
    service (#6) both compose, all sharing one decision_store as their
    own constructors require ("All collaborators must share the same
    stores the plan was built from" -- decision_impact_invalidation.py).
    One shared helper so build_recovery_decision_facade() and
    build_recovery_decision_health_service() never wire the same
    services twice.

    Left at their existing, already-safe defaults (None): the precondition
    revalidation / preflight invalidation / retry scheduling / chain
    reconciliation mechanisms (real implementations exist in sibling
    packages -- agent_task_recovery_guardrails, agent_task_queue_retry_scheduler
    -- but wiring cross-package integrations is a separate concern from
    CLI plumbing) and supersession chain-link recording. Every service
    here already fails closed, never guessed, when a mechanism or link is
    unconfigured -- this never adds a fallback of its own.
    """
    decision_store = decision_store or LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()

    impact = LLMAgentTaskRecoveryExecutionDecisionChangeImpactService(decision_store=decision_store)
    staleness = LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService()
    planner = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanService()
    plan_validation = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationPlanValidationService(
        impact_service=impact, staleness_service=staleness, plan_service=planner,
    )
    execution = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationService(
        decision_store=decision_store, impact_service=impact, staleness_service=staleness,
        plan_service=planner, plan_validation_service=plan_validation,
    )
    audit = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationAuditService()
    verification = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationVerificationService(
        audit_service=audit, decision_store=decision_store, impact_service=impact, staleness_service=staleness,
    )
    resolution = LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService(decision_store=decision_store)
    lifecycle = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleService(
        resolution_service=resolution, impact_service=impact, staleness_service=staleness, plan_service=planner,
        plan_validation_service=plan_validation, execution_service=execution, audit_service=audit,
        verification_service=verification,
    )
    lifecycle_results = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleResultService()
    lifecycle_verification = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleVerificationService(
        lifecycle_result_service=lifecycle_results, audit_service=audit, verification_service=verification,
        resolution_service=resolution,
    )
    reconciliation = LLMAgentTaskRecoveryExecutionDecisionImpactInvalidationLifecycleReconciliationService(
        lifecycle_result_service=lifecycle_results, lifecycle_verification_service=lifecycle_verification,
        lifecycle_service=lifecycle, resolution_service=resolution, impact_service=impact, staleness_service=staleness,
    )
    supersession_validation = LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService(
        decision_store=decision_store,
    )

    return SimpleNamespace(
        decision_store=decision_store, impact=impact, staleness=staleness, resolution=resolution,
        lifecycle=lifecycle, lifecycle_results=lifecycle_results, lifecycle_verification=lifecycle_verification,
        reconciliation=reconciliation, supersession_validation=supersession_validation,
    )


def build_recovery_decision_facade(decision_store=None):
    """Wire LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade (#1)."""
    c = _build_collaborators(decision_store)
    return LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade(
        supersession_validation_service=c.supersession_validation,
        lifecycle_service=c.lifecycle,
        lifecycle_result_service=c.lifecycle_results,
        lifecycle_verification_service=c.lifecycle_verification,
        reconciliation_service=c.reconciliation,
    )


def _build_health_stack(decision_store=None):
    """One shared build of the collaborators, #12's configuration
    validator, and #6's health service, all wired to the same
    decision_store -- used by both build_recovery_decision_health_service()
    and build_recovery_decision_readiness_service() so a caller wanting
    both never ends up with two different, disagreeing stores."""
    c = _build_collaborators(decision_store)
    configuration_validator = LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(
        decision_store=c.decision_store,
        resolution_service=c.resolution,
        supersession_validation_service=c.supersession_validation,
        impact_service=c.impact,
        staleness_service=c.staleness,
        lifecycle_result_service=c.lifecycle_results,
        lifecycle_verification_service=c.lifecycle_verification,
        lifecycle_service=c.lifecycle,
        reconciliation_service=c.reconciliation,
    )
    health_service = LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService(
        decision_store=c.decision_store,
        resolution_service=c.resolution,
        supersession_validation_service=c.supersession_validation,
        impact_service=c.impact,
        staleness_service=c.staleness,
        lifecycle_result_service=c.lifecycle_results,
        lifecycle_verification_service=c.lifecycle_verification,
        configuration_validator=configuration_validator,
    )
    return c, configuration_validator, health_service


def build_recovery_decision_health_service(decision_store=None):
    """Wire LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService
    (#6, which itself composes #7's dependency diagnostics and #12's
    configuration validator) -- read-only, never touches the lifecycle/
    reconciliation services' own run()/reconcile(). Passes an explicit
    configuration_validator built from the full nine-collaborator wiring
    (lifecycle_service and reconciliation_service included) rather than
    #6's own seven-collaborator default, so diagnose() reports a complete
    configuration verdict."""
    _, _, health_service = _build_health_stack(decision_store)
    return health_service


def build_recovery_decision_readiness_service(decision_store=None):
    """Wire LLMAgentTaskRecoveryExecutionDecisionLifecycleReadinessService
    (#13) from the same configuration validator (#12), health service
    (#6/#7), and lifecycle_result_service build_recovery_decision_health_service()
    itself uses -- never a second wiring of the same stack."""
    c, configuration_validator, health_service = _build_health_stack(decision_store)
    return LLMAgentTaskRecoveryExecutionDecisionLifecycleReadinessService(
        configuration_validator=configuration_validator,
        health_service=health_service,
        lifecycle_result_service=c.lifecycle_results,
    )


def build_recovery_decision_health_and_readiness_services(decision_store=None):
    """Wire the health service (#6) and the readiness service (#13) from ONE
    health stack: the readiness gate composes the very health service the
    diagnostics endpoint uses, instead of a second, identical wiring on its
    own store. Equivalent to calling build_recovery_decision_health_service()
    and build_recovery_decision_readiness_service() with a shared store."""
    c, configuration_validator, health_service = _build_health_stack(decision_store)
    readiness_service = LLMAgentTaskRecoveryExecutionDecisionLifecycleReadinessService(
        configuration_validator=configuration_validator,
        health_service=health_service,
        lifecycle_result_service=c.lifecycle_results,
    )
    return health_service, readiness_service
