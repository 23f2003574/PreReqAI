"""The `api-generation` commands of the PreReqAI CLI: `generate` (validated draft ->
FastAPI project) and `check` (health of a generated project). The recovery-decision
commands live in backend/cli.py, which registers and dispatches these."""

import argparse
import json
import sys

from backend.api_documentation_draft import LLMAPIDocumentationDraft, UnknownDraftError
from backend.api_generation import (
    APIGenerationConfig,
    DraftNotValidatedError,
    GeneratedArtifactRejectedError,
    InvalidDraftEndpointError,
    InvalidDraftInputError,
    InvalidGeneratorOutputError,
    UnknownGeneratedImportError,
    UnsafeGeneratedPathError,
    UnsafeOutputDirectoryError,
    check_generated_project,
    generate_application,
    load_draft_file,
    preflight_output_dir,
)
from backend.api_generation.project_manifest import artifact_type
from backend.cli_common import EXIT_FAILURE, EXIT_OK
from backend.llm.config import InvalidConfigurationError

# `api-generation generate` failure categories (see _generation_exit_code):
EXIT_INVALID_INPUT = 3  # the user can fix it: bad draft, configuration, output target
EXIT_GENERATION_FAILED = 4  # generation or generated-artifact validation (or writing) failed
EXIT_INTERNAL_ERROR = 5  # anything unexpected: a bug, not the user's input


def add_api_generation_parser(subparsers):
    api_generation = subparsers.add_parser(
        "api-generation",
        help="Generate a FastAPI project from a validated API documentation draft, and check generated projects",
        epilog="Worked example: examples/api-generation/ (walkthrough: docs/api-generation-walkthrough.md)",
    )
    api_generation_subparsers = api_generation.add_subparsers(dest="api_generation_command", required=True)
    generate = api_generation_subparsers.add_parser(
        "generate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="Generate, validate and write a FastAPI project from a validated API documentation draft",
        description=(
            "Turns one validated API documentation draft into a runnable FastAPI project (app package, OpenAPI\n"
            "document, requirements.txt, Dockerfile, README and project metadata). The draft is a JSON file with the\n"
            "fields of LLMAPIDocumentationDraft (draft_id, endpoint, summary, description, parameters, responses,\n"
            "examples, status); its status must be VALIDATED. Stages: configuration, preflight, input, generation,\n"
            "validation, write. The project is validated before anything is written."
        ),
        epilog=(
            "Example:\n"
            "  python -m backend.cli api-generation generate --draft examples/api-generation/draft.json \\\n"
            "      --output-dir ./loan-quote-api --dry-run      # preview; drop --dry-run to write\n"
            "\n"
            "Exit codes: 0 success; 2 usage error; 3 invalid input, configuration or output target;\n"
            "4 generation, validation or write failed; 5 unexpected internal error."
        ),
    )
    generate.add_argument("--draft", required=True, help="Path to the draft JSON file")
    generate.add_argument("--output-dir", required=True, help="Directory to write the generated project into")
    generate.add_argument("--base-image", default=None, help="Dockerfile base image (default: python:3.11-slim); overrides --config")
    generate.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Run every stage and report what would be generated, without writing anything",
    )
    generate.add_argument("--port", type=int, default=None, help="Dockerfile default listen port (default: 8000); overrides --config")
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
        help="Print one JSON summary on stdout, for success and failure alike: status, source, stages_completed, "
             "validation, warnings, dry_run and either the result (draft_id, endpoint, output_dir, files, openapi_path, "
             "artifact_types) or failed_stage and error",
    )
    generate.add_argument(
        "-q", "--quiet", action="store_true", dest="quiet",
        help="Do not print stage progress lines (progress is also off with --json)",
    )


    check = api_generation_subparsers.add_parser(
        "check",
        help="Check that a generated API project on disk is healthy (read-only; nothing is launched)",
        description="Validates a generated project directory (files, metadata, manifest, importable app, OpenAPI, "
                    "dependencies, README) and reports its compatibility with this generator version.",
        epilog="Exit codes: 0 healthy; 1 invalid or incompatible; 2 usage error.",
    )
    check.add_argument("project_dir", help="The generated project directory")
    check.add_argument("--json", action="store_true", dest="as_json", help="Print the health result as JSON")


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


_INVALID_INPUT_ERRORS = (
    InvalidConfigurationError, InvalidDraftInputError, UnsafeOutputDirectoryError, UnsafeGeneratedPathError,
    DraftNotValidatedError, UnknownDraftError, InvalidDraftEndpointError,
)
_GENERATION_ERRORS = (GeneratedArtifactRejectedError, InvalidGeneratorOutputError, UnknownGeneratedImportError)


def _generation_exit_code(error) -> int:
    """The one place a generate failure becomes a process exit code."""
    if isinstance(error, _INVALID_INPUT_ERRORS):
        return EXIT_INVALID_INPUT
    if isinstance(error, _GENERATION_ERRORS) or (isinstance(error, OSError) and _failure_stage(error) == "write"):
        return EXIT_GENERATION_FAILED
    return EXIT_INTERNAL_ERROR


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


def run_api_generation_generate(args) -> int:
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
        return _generation_exit_code(error)

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


def run_api_generation_check(args) -> int:
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


# Former private names, kept so existing imports (`from backend.cli import _run_api_generation_*`) keep working.
_run_api_generation_generate = run_api_generation_generate
_run_api_generation_check = run_api_generation_check
