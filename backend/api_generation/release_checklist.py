import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, replace

from backend.api_documentation_draft import LLMAPIDocumentationDraft, LLMAPIDocumentationDraftService

from .fastapi_generator import FastAPIApplicationGenerator
from .generator import APIGenerator
from .service import DraftNotValidatedError, LLMAPIGenerationService
from .validation import GeneratedArtifactRejectedError, validate_generated_artifact
from .workflow import generate_application

_CATEGORY_GROUPS = {
    "generated artifacts pass validation": None,  # any finding
    "metadata and manifest are present and consistent": {
        "INVALID_METADATA", "METADATA_MISMATCH", "INVALID_MANIFEST", "MANIFEST_ARTIFACTS", "MANIFEST_CONFIGURATION", "IDENTITY_MISMATCH",
        "INCOMPATIBLE_PROJECT",
    },
    "generated application can be imported": {"SYNTAX_ERROR", "IMPORT_ERROR", "NO_ENTRYPOINT", "NO_ROUTES"},
    "OpenAPI contract is available": {"OPENAPI_ERROR", "OPENAPI_MISMATCH", "OPENAPI_FILE_MISMATCH"},
    "README references the actual artifacts": {"README_INCOMPLETE"},
}
_REQUIRED_TARGETS = {
    "metadata and manifest are present and consistent": {"prereqai-project.json", "prereqai-manifest.json"},
    "OpenAPI contract is available": {"openapi.json"},
    "README references the actual artifacts": {"README.md"},
    "generated application can be imported": {"app/main.py", "app/__init__.py"},
}


@dataclass(frozen=True)
class LLMGenerationReleaseChecklist:
    """Structured outcome of run_release_checklist(): ready is True only when
    no check failed; checks is [{"name", "status"}] in a fixed order (status passed, failed, or
    skipped when a prerequisite already failed);
    failures and warnings are plain "name: detail" strings (warnings never
    block a release)."""

    ready: bool
    checks: list
    failures: list
    warnings: list

    def to_dict(self) -> dict:
        return asdict(self)


def run_release_checklist(
    draft_service: LLMAPIDocumentationDraftService, draft: LLMAPIDocumentationDraft, generator: APIGenerator = None,
) -> LLMGenerationReleaseChecklist:
    """Verify the generation guarantees for one validated draft without
    writing anything: generation and validation run in memory, dry-run and
    failure paths are exercised against an output path that is never
    created, and every file-level check reuses validate_generated_artifact()
    rather than re-implementing it."""
    generator = generator or FastAPIApplicationGenerator()
    checks, failures = [], []

    def record(name, problems):
        checks.append({"name": name, "status": "failed" if problems else "passed"})
        failures.extend(f"{name}: {problem}" for problem in problems)

    def attempt(name, check):
        try:
            record(name, check())
        except Exception as error:  # a broken stage is a failed check, never a traceback
            record(name, [f"{type(error).__name__}: {error}"])

    probe = os.path.join(tempfile.gettempdir(), f"prereqai-release-check-{uuid.uuid4().hex}")  # never created

    def entrypoint():
        from backend.cli import _build_parser

        args = _build_parser().parse_args(["api-generation", "generate", "--draft", "d.json", "--output-dir", "o", "--dry-run"])
        return [] if args.dry_run and args.api_generation_command == "generate" else ["generate command is not wired"]

    def validated_required():
        try:
            generate_application(draft_service, replace(draft, status="DRAFT"), probe, generator=generator, dry_run=True)
        except DraftNotValidatedError:
            return []
        return ["an unvalidated draft was accepted for generation"]

    attempt("workflow is reachable through the supported entrypoint", entrypoint)
    attempt("validated input is required before generation", validated_required)

    try:
        files = LLMAPIGenerationService(draft_service, generator).generate(draft).files
        findings = validate_generated_artifact(files).findings
    except Exception as error:
        files, findings = {}, [{"category": "GENERATION_ERROR", "target": "-", "message": f"{type(error).__name__}: {error}"}]

    for name, categories in _CATEGORY_GROUPS.items():
        targets = _REQUIRED_TARGETS.get(name, set())
        relevant = [
            f for f in findings
            if categories is None or f["category"] in categories or f["category"] == "GENERATION_ERROR"
            or (f["category"] in {"MISSING_FILE", "EMPTY_FILE"} and f["target"] in targets)
        ]
        record(name, [f"{f['category']} {f['target']}: {f['message']}" for f in relevant])

    def dry_run_is_faithful():
        planned = generate_application(draft_service, draft, probe, generator=generator, dry_run=True)
        problems = [] if planned.files == sorted(files) else ["dry run lists different files than generation produces"]
        return problems + (["dry run created the output path"] if os.path.exists(probe) else [])

    class _Broken(APIGenerator):
        def generate(self, draft):
            return {**generator.generate(draft), "app/main.py": "def broken(:\n"}

    def failure_leaves_nothing():
        try:
            generate_application(draft_service, draft, probe, generator=_Broken())
        except GeneratedArtifactRejectedError:
            return [] if not os.path.exists(probe) else ["a rejected generation left output behind"]
        return ["a corrupted generation was accepted"]

    warnings = ["container build: the Dockerfile is checked structurally only; run `docker build` to verify the image"]
    if findings:  # an invalid generation is rejected by the dry run too; that is already reported above
        checks.append({"name": "dry run does not mutate output", "status": "skipped"})
        warnings.append("dry run check skipped: generation is invalid")
    else:
        attempt("dry run does not mutate output", dry_run_is_faithful)
    attempt("failure paths leave no misleading artifacts", failure_leaves_nothing)

    return LLMGenerationReleaseChecklist(ready=not failures, checks=checks, failures=failures, warnings=warnings)
