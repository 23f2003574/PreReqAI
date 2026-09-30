from dataclasses import dataclass
from pathlib import Path

from backend.api_documentation_draft import LLMAPIDocumentationDraft, LLMAPIDocumentationDraftService

from .fastapi_generator import FastAPIApplicationGenerator
from .generator import APIGenerator
from .openapi import write_openapi_contract
from .service import LLMAPIGenerationService
from .validation import require_valid
from .writer import write_generated_application


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


STAGES = ("generation", "validation", "write", "openapi")


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


def generate_application(
    draft_service: LLMAPIDocumentationDraftService,
    draft: LLMAPIDocumentationDraft,
    output_dir,
    generator: APIGenerator = None,
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
    result = _stage("generation", LLMAPIGenerationService(draft_service, generator or FastAPIApplicationGenerator()).generate, draft)
    _stage("validation", require_valid, result.files)
    written = _stage("write", write_generated_application, result, output_dir)
    openapi_path = _stage("openapi", write_openapi_contract, result, output_dir)
    return LLMGeneratedApplication(
        draft_id=result.draft_id, endpoint=result.endpoint, output_dir=Path(output_dir).resolve(),
        files=written, openapi_path=openapi_path,
    )
