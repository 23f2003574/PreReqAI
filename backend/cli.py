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
from backend.api_documentation_draft import LLMAPIDocumentationDraft
from backend.api_generation import (
    APIGenerationConfig,
    GeneratedArtifactRejectedError,
    UnsafeOutputDirectoryError,
    check_generated_project,
    generate_application,
    load_draft_file,
    preflight_output_dir,
)
from backend.api_generation.project_manifest import artifact_type
from backend.llm.config import InvalidConfigurationError

_SUCCESS_STATUSES = (IMPACT_LIFECYCLE_REMEDIATED, IMPACT_LIFECYCLE_CLEAN, IMPACT_LIFECYCLE_UP_TO_DATE)

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_USAGE = 2


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


def _add_api_generation_parser(subparsers):
    api_generation = subparsers.add_parser(
        "api-generation", help="Generated API application operations",
        epilog="Worked example: examples/api-generation/ (walkthrough: docs/api-generation-walkthrough.md)",
    )
    api_generation_subparsers = api_generation.add_subparsers(dest="api_generation_command", required=True)
    generate = api_generation_subparsers.add_parser(
        "generate",
        help="Generate, validate and write a FastAPI project from a validated API documentation draft",
        description=(
            "Reads a JSON file holding one API documentation draft (the fields of LLMAPIDocumentationDraft: "
            "draft_id, endpoint, summary, description, parameters, responses, examples, status). The draft's "
            "status must be VALIDATED; a DRAFT is rejected. The project is validated before anything is written."
        ),
    )
    generate.add_argument("--draft", required=True, help="Path to the draft JSON file")
    generate.add_argument("--output-dir", required=True, help="Directory to write the generated project into")
    generate.add_argument("--base-image", default=None, help="Dockerfile base image (default: python:3.11-slim)")
    generate.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Run every stage and report what would be generated, without writing anything",
    )
    generate.add_argument("--port", type=int, default=None, help="Dockerfile default listen port (default: 8000)")
    generate.add_argument(
        "--config", default=None,
        help="A prereqai-config.json (e.g. from an earlier generated project) holding base_image, port and "
             "project_name; explicit flags override its values",
    )
    generate.add_argument(
        "--project-name", default=None, dest="project_name",
        help="Project name (letters, digits, '-', '_'); the app is generated in the package it normalizes to, "
             "e.g. loan-quote -> loan_quote/main.py (default: the draft's summary, package app)",
    )
    generate.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Print the result (draft_id, endpoint, output_dir, files, openapi_path) as JSON",
    )
    generate.add_argument(
        "-q", "--quiet", action="store_true", dest="quiet",
        help="Do not print stage progress lines (progress is also off with --json)",
    )


    check = api_generation_subparsers.add_parser(
        "check", help="Check that a generated API project on disk is healthy (read-only; nothing is launched)",
    )
    check.add_argument("project_dir", help="The generated project directory")
    check.add_argument("--json", action="store_true", dest="as_json", help="Print the health result as JSON")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prereqai", description="PreReqAI command-line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_recovery_decision_parser(subparsers)
    _add_api_generation_parser(subparsers)
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
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FAILURE

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
        print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        return EXIT_FAILURE

    if args.as_json:
        print(json.dumps(result.to_dict(), indent=2, default=str, sort_keys=True))
    else:
        print(_format_readiness_human(result))

    # Same non-success diagnostic convention as `evaluate`/`diagnose`:
    # only READY is EXIT_OK; BLOCKED is EXIT_FAILURE.
    return EXIT_OK if result.status == READY else EXIT_FAILURE


class _LoadedDraftSource:
    """The one draft the CLI was given. It plays the draft service's get()
    role for the generation boundary, which still rejects any draft whose
    status is not VALIDATED."""

    def __init__(self, draft):
        self._draft = draft

    def get(self, draft_id):
        return self._draft


def _load_draft(path) -> LLMAPIDocumentationDraft:
    return load_draft_file(path)


def _build_config(args) -> APIGenerationConfig:
    options = {k: v for k, v in (("base_image", args.base_image), ("port", args.port),
                                ("project_name", args.project_name)) if v is not None}
    if args.config is not None:
        config = APIGenerationConfig.from_file(args.config, args.output_dir, overrides=options)
    else:
        config = APIGenerationConfig(output_dir=args.output_dir, **options)
    return config.validate()


def _cli_stage(name, progress, call, *args):
    """Run one pre-generation CLI stage, reporting it like the workflow's own."""
    try:
        value = call(*args)
    except Exception:
        progress(name, "failed")
        raise
    progress(name, "ok")
    return value


def _preflight(config):
    try:
        preflight_output_dir(config.output_dir)
    except Exception as error:
        error.stage = "preflight"
        raise


_GENERATION_HINTS = {
    "input": "pass a JSON file with the fields of an API documentation draft (see examples/api-generation/draft.json)",
    "configuration": "fix the option or the --config file and run again; nothing was written",
    "preflight": "choose an output directory that can be created and written; nothing was written",
    "generation": "the draft must be VALIDATED and describe a supported endpoint; nothing was written",
    "validation": "the generated project was rejected before writing; nothing was written",
    "write": "use an empty output directory, or one this tool generated earlier",
}


def _failure_stage(error) -> str:
    stage = getattr(error, "stage", None)
    if stage is None:  # raised before generate_application(): the config file/flags or the draft file
        stage = "configuration" if isinstance(error, InvalidConfigurationError) else "input"
    return stage


def _generation_summary(args, completed, application=None, error=None) -> dict:
    """The one final summary of a generate run, from what the pipeline already
    knows: the source draft file, the stages that completed, the output
    location and artifact types, validation status, warnings (the pipeline
    produces none) and, on failure, the failing stage and reason."""
    failed_stage = _failure_stage(error) if error is not None else None
    summary = {
        "status": "failed" if error is not None else "success",
        "source": args.draft, "stages_completed": list(completed), "dry_run": bool(args.dry_run),
        "validation": "failed" if failed_stage == "validation" else ("passed" if "validation" in completed else "not run"),
        "warnings": [],
    }
    if application is not None:
        summary.update(application.to_dict())
        summary["artifact_types"] = sorted({artifact_type(path) for path in application.files if artifact_type(path)})
    else:
        summary.update({"failed_stage": failed_stage, "error": {"type": type(error).__name__, "message": str(error)}})
    return summary


def _report_generation_failure(error):
    """One error format for every generation failure: the failing stage, the
    exception type and reason, the underlying cause when there is one, and an
    actionable hint. The original exception is not altered or replaced."""
    stage = _failure_stage(error)
    kind = "output conflict" if isinstance(error, UnsafeOutputDirectoryError) else "generation failed"
    print(f"error: {kind} at stage '{stage}': {type(error).__name__}: {error}", file=sys.stderr)
    if isinstance(error, GeneratedArtifactRejectedError):
        for finding in error.validation.findings:
            print(f"  - {finding['category']} {finding['target']}: {finding['message']}", file=sys.stderr)
    cause = error.__cause__
    if cause is not None:
        print(f"  caused by: {type(cause).__name__}: {cause}", file=sys.stderr)
    hint = _GENERATION_HINTS.get(stage)
    if hint:
        print(f"  hint: {hint}", file=sys.stderr)


def _run_api_generation_generate(args) -> int:
    """generate_application() with the CLI's conventions: results on stdout
    (--json for the machine-readable form), failures as `error: ...` on
    stderr naming the failing stage and exit code 1, never a stack trace."""
    show = not (args.quiet or args.as_json)

    completed = []

    def progress(stage, status):
        if status == "ok":
            completed.append(stage)
        if show:
            note = " (dry run: nothing written)" if stage == "write" and args.dry_run and status == "ok" else ""
            print(f"[{status}] {stage}{note}")

    try:
        config = _cli_stage("configuration", progress, _build_config, args)  # before the draft is read
        _cli_stage("preflight", progress, _preflight, config)
        draft = _cli_stage("input", progress, _load_draft, args.draft)
        application = generate_application(
            _LoadedDraftSource(draft), draft, config=config, dry_run=args.dry_run,
            progress=lambda stage, status: progress(stage, status) if stage not in ("configuration", "preflight") else None,
        )
    except Exception as error:  # never leak a composed service's internals as a stack trace by default
        _report_generation_failure(error)
        if args.as_json:
            print(json.dumps(_generation_summary(args, completed, error=error), indent=2, sort_keys=True))
        else:
            print(f"Result: failed at stage '{_failure_stage(error)}' (completed: {', '.join(completed) or 'none'})")
        return EXIT_FAILURE

    summary = _generation_summary(args, completed, application=application)
    if args.as_json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    elif application.dry_run:
        print(f"Dry run: would generate {application.endpoint} (draft {application.draft_id})")
        print(f"  output:  {application.output_dir}")
        print("  files:   " + ", ".join(application.files))
        print("  no files were written")
    else:
        print(f"Generated {application.endpoint} (draft {application.draft_id})")
        print(f"  output:  {application.output_dir}")
        print("  files:   " + ", ".join(application.files))
        print(f"  openapi: {application.openapi_path}")
        print(f"  run:     cd {application.output_dir} && uvicorn app.main:app")
    if not args.as_json:
        print(f"Result: success ({len(summary['stages_completed'])} stages completed, validation {summary['validation']}; "
              f"artifacts: {', '.join(summary['artifact_types'])})")
    return EXIT_OK


def _run_api_generation_check(args) -> int:
    """check_generated_project() with the diagnostic-command conventions:
    only a healthy project is EXIT_OK, anything else is EXIT_FAILURE."""
    health = check_generated_project(args.project_dir)
    if args.as_json:
        print(json.dumps(health.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"Project health: {health.status.upper()}")
        for name, outcome in health.checks.items():
            print(f"  {name}: {outcome}")
        for finding in health.findings:
            print(f"  - {finding['category']} {finding['target']}: {finding['message']}")
        compatibility = health.compatibility
        print(f"Compatibility: {compatibility['status'].upper()}")
        for file, fields in compatibility["detected"].items():
            supported = compatibility["supported"][file]
            print("  " + file + ": " + ", ".join(
                f"{field} {'-' if found is None else found} (supported {supported[field]})" for field, found in fields.items()))
        regeneration = compatibility.get("regeneration")
        if regeneration:
            print("Regeneration recommended (informational; nothing was changed):")
            for version in regeneration["versions"]:
                print(f"  {version['file']} {version['field']}: project {version['project']}, "
                      f"generator {version['generator']}")
            print(f"  run: {regeneration['command']}")
            print(f"  note: {regeneration['note']}")
        elif compatibility["remediation"]:
            print(f"  fix: {compatibility['remediation']}")
    return EXIT_OK if health.healthy else EXIT_FAILURE


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
        return _run_api_generation_generate(args)

    if args.command == "api-generation" and args.api_generation_command == "check":
        return _run_api_generation_check(args)

    parser.print_usage(sys.stderr)
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
