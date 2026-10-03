from dataclasses import dataclass
from pathlib import Path

from backend.api_documentation_draft import LLMAPIDocumentationDraft, LLMAPIDocumentationDraftService

from .config import APIGenerationConfig
from .fastapi_generator import FastAPIApplicationGenerator
from .generator import APIGenerator
from .openapi import OPENAPI_FILENAME
from .service import LLMAPIGenerationService
from .validation import require_valid
from .writer import plan_write, preflight_output_dir, write_generated_application


@dataclass(frozen=True)
class LLMGeneratedApplication:
    """A generated, validated application written to output_dir. files are
    the relative paths written; openapi_path is the generated app's own
    OpenAPI contract."""

    draft_id: str
    endpoint: str
    output_dir: Path
    files: list
    openapi_path: Path
    dry_run: bool = False


STAGES = ("configuration", "preflight", "generation", "validation", "write")


def _stage(name, call, *args):
    """Run one pipeline stage. A failure is re-raised unchanged (so callers
    keep catching the specific error types) but tagged with `.stage` and a
    traceback note saying which stage failed; only a return from every stage
    yields a LLMGeneratedApplication."""
    try:
        return call(*args)
    except Exception as error:
        error.stage = name
        error.add_note(f"API generation failed at stage: {name}")
        raise


def _notify(progress, stage, status):
    if progress is not None:
        try:
            progress(stage, status)
        except Exception:  # reporting must never change the pipeline's outcome
            pass


def _tag(error, name):
    error.stage = name
    return error


def generate_application(
    draft_service: LLMAPIDocumentationDraftService,
    draft: LLMAPIDocumentationDraft,
    output_dir=None,
    generator: APIGenerator = None,
    config: APIGenerationConfig = None,
    dry_run: bool = False,
    progress=None,
) -> LLMGeneratedApplication:
    """The step after a validated documentation draft: generate the
    application (#2 boundary), validate the generated files (#10) and only
    then write them (#6) with the OpenAPI contract (#7).

    Raises DraftNotValidatedError / UnknownDraftError (boundary),
    InvalidDraftEndpointError / UnknownGeneratedImportError (generator) or
    GeneratedArtifactRejectedError (validation) before anything is written,
    so a generation or validation failure never leaves partial output behind.
    Every failure carries `.stage` (one of STAGES); a write-stage failure may
    leave a partially written directory but is never returned as a success. Callers that only want
    the documentation draft are unaffected: the draft service is unchanged."""
    def run(name, call, *args):
        try:
            value = _stage(name, call, *args)
        except Exception:
            _notify(progress, name, "failed")
            raise
        _notify(progress, name, "ok")
        return value

    if config is not None:
        run("configuration", config.validate)
        if output_dir is not None and Path(output_dir) != Path(config.output_dir):
            raise _tag(ValueError("output_dir conflicts with config.output_dir; pass only one"), "configuration")
        output_dir = config.output_dir
        generator = generator or FastAPIApplicationGenerator(config.base_image, config.port, config.project_name)
    elif output_dir is None:
        raise _tag(ValueError("output_dir or config is required"), "configuration")
    run("preflight", preflight_output_dir, output_dir)  # before any generation work
    result = run("generation", LLMAPIGenerationService(draft_service, generator or FastAPIApplicationGenerator()).generate, draft)
    run("validation", require_valid, result.files)
    if dry_run:
        root, targets, _ = run("write", plan_write, result, output_dir)  # the real write's read-only checks
        written = sorted(targets)
    else:
        written = run("write", write_generated_application, result, output_dir)
    openapi_path = Path(output_dir).resolve() / OPENAPI_FILENAME
    return LLMGeneratedApplication(
        draft_id=result.draft_id, endpoint=result.endpoint, output_dir=Path(output_dir).resolve(),
        files=written, openapi_path=openapi_path, dry_run=dry_run,
    )
