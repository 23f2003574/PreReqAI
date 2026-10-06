"""PreReqAI command-line entrypoint.

The repository had no CLI before this: no argument-parsing framework is
declared anywhere in requirements.txt, and no `__main__`/console_scripts
entrypoint existed. This adds one using only Python's standard-library
argparse (no new dependency, nothing that could compete with a CLI
framework that isn't there), following the one convention the codebase
does already establish everywhere else in this package: every public
result already has a deterministic to_dict() (see AgentTaskRecoveryExecutionDecisionLifecycleResult,
models.py) -- `--json` reuses that verbatim as this CLI's machine-readable
mode, rather than inventing a second, competing shape.

Usage:
    python -m backend.cli recovery-decision evaluate <task-id> [--json]
"""

import argparse
import json
import sys
from types import SimpleNamespace

from backend.agent_task_recovery_execution_precondition_snapshots import (
    HEALTH_HEALTHY,
    IMPACT_LIFECYCLE_CLEAN,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UP_TO_DATE,
    LIFECYCLE_VERIFICATION_VALID,
    READY,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError,
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
from backend.cli_api_generation import (  # noqa: F401  (re-exported: the CLI's public names stay importable from backend.cli)
    EXIT_GENERATION_FAILED,
    EXIT_INTERNAL_ERROR,
    EXIT_INVALID_INPUT,
    _generation_exit_code,
    _load_draft,
    _run_api_generation_check,
    _run_api_generation_generate,
    add_api_generation_parser,
    run_api_generation_check,
    run_api_generation_generate,
)
from backend.cli_common import EXIT_FAILURE, EXIT_OK, EXIT_USAGE  # noqa: F401
from backend.cli_prerequisites import (
    add_prerequisites_parser,
    run_prerequisites_analyze,
)

_SUCCESS_STATUSES = (IMPACT_LIFECYCLE_REMEDIATED, IMPACT_LIFECYCLE_CLEAN, IMPACT_LIFECYCLE_UP_TO_DATE)



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


def _is_success(result) -> bool:
    """A lifecycle counts as successful only when its own status is one
    of the non-blocking outcomes, verification agrees, and nothing is
    still reported blocking -- the same three signals a caller would
    otherwise have to check by hand across three separate result
    objects."""
    return (
        result.overall_status in _SUCCESS_STATUSES
        and result.verification_status == LIFECYCLE_VERIFICATION_VALID
        and not result.blocking_conditions
    )


def _report_unexpected_failure(verb, error) -> int:
    """One message for an unexpected recovery-decision failure, matching the
    HTTP API's wording ("Failed to <verb> the recovery execution decision
    lifecycle") with the underlying reason and a next step."""
    print(f"error: failed to {verb} the recovery execution decision lifecycle: {type(error).__name__}: {error}",
          file=sys.stderr)
    print("  hint: run `recovery-decision readiness` to check configuration and dependencies", file=sys.stderr)
    return EXIT_FAILURE


def _format_human(result) -> str:
    lines = [
        f"authoritative decision: {result.authoritative_decision_id}",
        f"lineage status: {result.decision_lineage_status}",
        "affected artifacts: " + (", ".join(result.affected_artifacts) if result.affected_artifacts else "none"),
        f"remediation operation id: {result.remediation_operation_id}",
        f"reconciliation operation id: {result.reconciliation_operation_id}",
        "blockers: " + (", ".join(result.blocking_conditions) if result.blocking_conditions else "none"),
        f"verification status: {result.verification_status}",
        f"overall status: {result.overall_status}",
    ]
    return "\n".join(lines)


def _format_health_human(result) -> str:
    lines = [
        f"overall status: {result.status}",
        f"authoritative decision: {result.authoritative_decision_id}",
        f"latest lifecycle result: {result.latest_lifecycle_result_id}",
        "dependencies:",
    ]
    for dependency in result.dependency_diagnostics:
        reason = dependency.failure_reason if dependency.failure_reason is not None else "none"
        lines.append(
            f"  - {dependency.dependency}: {dependency.status} "
            f"(blocking={dependency.blocking}) reason={reason} last_verified={dependency.last_verified_state}"
        )
    return "\n".join(lines)


def _format_readiness_human(result) -> str:
    lines = [
        f"status: {result.status}",
        f"configuration status: {result.configuration_status}",
        f"dependency status: {result.dependency_status}",
        f"decision lineage status: {result.decision_lineage_status}",
        f"verification status: {result.verification_status}",
        "blocking conditions: " + (", ".join(result.blocking_conditions) if result.blocking_conditions else "none"),
        "issues: " + ("; ".join(result.issues) if result.issues else "none"),
    ]
    return "\n".join(lines)


def _add_recovery_decision_parser(subparsers):
    recovery_decision = subparsers.add_parser(
        "recovery-decision", help="Recovery execution decision lifecycle operations",
    )
    recovery_decision_subparsers = recovery_decision.add_subparsers(dest="recovery_decision_command", required=True)

    evaluate = recovery_decision_subparsers.add_parser(
        "evaluate",
        help="Evaluate a task's recovery execution decision lifecycle end to end",
    )
    evaluate.add_argument("task_id", help="The task id to evaluate")
    evaluate.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Print the machine-readable result contract (AgentTaskRecoveryExecutionDecisionLifecycleResult.to_dict()) as JSON",
    )

    diagnose = recovery_decision_subparsers.add_parser(
        "diagnose",
        help=(
            "Diagnostic-only: report the health of a task's recovery execution decision "
            "lifecycle and its dependencies, without evaluating or changing anything"
        ),
    )
    diagnose.add_argument("task_id", help="The task id to diagnose")
    diagnose.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Print the machine-readable result contract (AgentTaskRecoveryExecutionDecisionLifecycleHealthResult.to_dict()) as JSON",
    )

    readiness = recovery_decision_subparsers.add_parser(
        "readiness",
        help=(
            "Deploy/CI readiness gate: composes configuration validation, dependency "
            "diagnostics, and (if a task id is given) that task's lifecycle health into "
            "one ready/blocked verdict. Diagnostic-only -- never evaluates or changes anything"
        ),
    )
    readiness.add_argument("task_id", nargs="?", default=None, help="Optional task id to include in the readiness check")
    readiness.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Print the machine-readable result contract (AgentTaskRecoveryExecutionDecisionLifecycleReadinessResult.to_dict()) as JSON",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prereqai", description="PreReqAI command-line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_recovery_decision_parser(subparsers)
    add_api_generation_parser(subparsers)
    add_prerequisites_parser(subparsers)
    return parser


def _run_recovery_decision_evaluate(args, facade) -> int:
    facade = facade if facade is not None else build_recovery_decision_facade()
    try:
        result = facade.evaluate(args.task_id)
    except InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILURE
    except Exception as error:  # never leak a composed service's internals as a stack trace by default
        return _report_unexpected_failure("evaluate", error)

    if args.as_json:
        print(json.dumps(result.to_dict(), indent=2, default=str, sort_keys=True))
    else:
        print(_format_human(result))

    return EXIT_OK if _is_success(result) else EXIT_FAILURE


def _run_recovery_decision_diagnose(args, health_service) -> int:
    """Diagnostic-only: calls LLMAgentTaskRecoveryExecutionDecisionLifecycle
    HealthService.check() (#6, which itself composes #7's per-dependency
    diagnostics) -- never facade.evaluate(), so this command can never
    execute remediation/recovery or change any persisted state."""
    health_service = health_service if health_service is not None else build_recovery_decision_health_service()
    try:
        result = health_service.check(args.task_id)
    except InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILURE
    except Exception as error:  # never leak a composed service's internals as a stack trace by default
        return _report_unexpected_failure("diagnose", error)

    if args.as_json:
        print(json.dumps(result.to_dict(), indent=2, default=str, sort_keys=True))
    else:
        print(_format_health_human(result))

    # Same non-success diagnostic convention as `evaluate`: only a clean
    # HEALTH_HEALTHY verdict is EXIT_OK; degraded/blocked/unavailable are
    # all EXIT_FAILURE -- there is no third exit code family to invent.
    return EXIT_OK if result.status == HEALTH_HEALTHY else EXIT_FAILURE


def _run_recovery_decision_readiness(args, readiness_service) -> int:
    """Diagnostic-only: calls LLMAgentTaskRecoveryExecutionDecisionLifecycle
    ReadinessService.check() (#13, which itself composes #12's
    configuration validator and #6/#7's health/dependency diagnostics) --
    never facade.evaluate() and never lifecycle_service.run()/
    reconciliation_service.reconcile(), so this command can never execute
    remediation/recovery or change any persisted state."""
    readiness_service = readiness_service if readiness_service is not None else build_recovery_decision_readiness_service()
    try:
        result = readiness_service.check(args.task_id)
    except InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILURE
    except Exception as error:  # never leak a composed service's internals as a stack trace by default
        return _report_unexpected_failure("compute readiness for", error)

    if args.as_json:
        print(json.dumps(result.to_dict(), indent=2, default=str, sort_keys=True))
    else:
        print(_format_readiness_human(result))

    # Same non-success diagnostic convention as `evaluate`/`diagnose`:
    # only READY is EXIT_OK; BLOCKED is EXIT_FAILURE.
    return EXIT_OK if result.status == READY else EXIT_FAILURE


def main(argv=None, facade=None, health_service=None, readiness_service=None) -> int:
    """Entry point. `facade`/`health_service`/`readiness_service`, when
    given, replace build_recovery_decision_facade()/
    build_recovery_decision_health_service()/
    build_recovery_decision_readiness_service() -- used by tests to
    exercise CLI parsing/formatting/exit-code behavior against a known
    result without re-deriving the full service wiring, the same
    fixture-reuse approach this package's own test suites already use."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "recovery-decision" and args.recovery_decision_command == "evaluate":
        return _run_recovery_decision_evaluate(args, facade)
    if args.command == "recovery-decision" and args.recovery_decision_command == "diagnose":
        return _run_recovery_decision_diagnose(args, health_service)
    if args.command == "recovery-decision" and args.recovery_decision_command == "readiness":
        return _run_recovery_decision_readiness(args, readiness_service)

    if args.command == "api-generation" and args.api_generation_command == "generate":
        return run_api_generation_generate(args)
    if args.command == "api-generation" and args.api_generation_command == "check":
        return run_api_generation_check(args)

    if args.command == "prerequisites" and args.prerequisites_command == "analyze":
        return run_prerequisites_analyze(args)

    parser.print_usage(sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
