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

from backend.agent_task_recovery_execution_precondition_snapshots import (
    IMPACT_LIFECYCLE_CLEAN,
    IMPACT_LIFECYCLE_REMEDIATED,
    IMPACT_LIFECYCLE_UP_TO_DATE,
    LIFECYCLE_VERIFICATION_VALID,
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
    LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionResolutionService,
    LLMAgentTaskRecoveryExecutionDecisionSupersessionValidationService,
    LLMAgentTaskRecoveryExecutionPreconditionDecisionStore,
    InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError,
)

_SUCCESS_STATUSES = (IMPACT_LIFECYCLE_REMEDIATED, IMPACT_LIFECYCLE_CLEAN, IMPACT_LIFECYCLE_UP_TO_DATE)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2


def build_recovery_decision_facade(decision_store=None):
    """Wire LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade from the
    existing #1-#10 services in this package, all sharing one
    decision_store as their own constructors require ("All collaborators
    must share the same stores the plan was built from" --
    decision_impact_invalidation.py).

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

    return LLMAgentTaskRecoveryExecutionDecisionLifecycleFacade(
        supersession_validation_service=supersession_validation,
        lifecycle_service=lifecycle,
        lifecycle_result_service=lifecycle_results,
        lifecycle_verification_service=lifecycle_verification,
        reconciliation_service=reconciliation,
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prereqai", description="PreReqAI command-line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_recovery_decision_parser(subparsers)
    return parser


def _run_recovery_decision_evaluate(args, facade) -> int:
    facade = facade if facade is not None else build_recovery_decision_facade()
    try:
        result = facade.evaluate(args.task_id)
    except InvalidAgentTaskRecoveryExecutionDecisionLifecycleFacadeError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_FAILURE
    except Exception as error:  # never leak a composed service's internals as a stack trace by default
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FAILURE

    if args.as_json:
        print(json.dumps(result.to_dict(), indent=2, default=str, sort_keys=True))
    else:
        print(_format_human(result))

    return EXIT_OK if _is_success(result) else EXIT_FAILURE


def main(argv=None, facade=None) -> int:
    """Entry point. `facade`, when given, replaces
    build_recovery_decision_facade() -- used by tests to exercise CLI
    parsing/formatting/exit-code behavior against a known result without
    re-deriving the full service wiring, the same fixture-reuse approach
    this package's own test suites already use."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "recovery-decision" and args.recovery_decision_command == "evaluate":
        return _run_recovery_decision_evaluate(args, facade)

    parser.print_usage(sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
