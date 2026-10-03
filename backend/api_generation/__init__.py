"""Notebook2API API generation: a validated API documentation draft in, a
validated, runnable FastAPI project out.

Supported entrypoint (everything else is a lower-level building block):

    python -m backend.cli api-generation generate --draft draft.json --output-dir DIR [--dry-run]
    python -m backend.cli api-generation check DIR

which calls generate_application() / check_generated_project(). The CLI reads
the draft as JSON because the notebook-analysis -> draft services
(backend.notebook_analysis ... backend.api_documentation_draft) need an LLM
provider and are composed by the caller; their output is
LLMAPIDocumentationDraft, the one input this package accepts.

Lower-level APIs, kept for callers and tests: LLMAPIGenerationService (the
validated-draft boundary), FastAPIApplicationGenerator, validate_generated_artifact /
require_valid, write_generated_application, write_openapi_contract,
run_release_checklist.
"""
from .config import CONFIG_FILENAME, APIGenerationConfig, IncompatibleConfigurationError
from .docker import ASGI_SERVER, InvalidDockerInputError, generate_dockerfile
from .fastapi_generator import FastAPIApplicationGenerator, InvalidDraftEndpointError
from .draft_input import InvalidDraftInputError, load_draft_file
from .generator import APIGenerator
from .identity import (
    DEFAULT_PACKAGE,
    InvalidProjectNameError,
    ProjectIdentity,
    project_package,
    resolve_project_identity,
)
from .health import HEALTHY, INCOMPATIBLE, INVALID, LLMGeneratedProjectHealth, check_generated_project
from .metadata import (
    IncompatibleProjectMetadataError,
    CONTRACT_VERSION,
    GENERATOR_ID,
    METADATA_FILENAME,
    GeneratedProjectMetadata,
    InvalidProjectMetadataError,
)
from .project_manifest import (
    IncompatibleProjectManifestError,
    ENTRYPOINT,
    MANIFEST_VERSION,
    PROJECT_MANIFEST_FILENAME,
    GeneratedProjectManifest,
    InvalidProjectManifestError,
)
from .readme import README_FILENAME, generate_readme
from .models import LLMAPIGenerationResult
from .validation import (
    GeneratedArtifactRejectedError,
    LLMGeneratedArtifactValidation,
    require_valid,
    validate_generated_artifact,
)
from .workflow import STAGES, LLMGeneratedApplication, generate_application
from .writer import (
    COMPLETE,
    INCOMPLETE,
    MARKER_FILENAME,
    UnsafeGeneratedPathError,
    UnsafeOutputDirectoryError,
    generation_status,
    plan_write,
    write_generated_application,
)
from .manifest import UnknownGeneratedImportError, generate_requirements
from .openapi import OPENAPI_FILENAME, generated_openapi, write_openapi_contract
from .release_checklist import LLMGenerationReleaseChecklist, run_release_checklist
from .service import DraftNotValidatedError, InvalidGeneratorOutputError, LLMAPIGenerationService

__all__ = [
    "InvalidDraftInputError",
    "load_draft_file",
    "IncompatibleConfigurationError",
    "CONFIG_FILENAME",
    "DEFAULT_PACKAGE",
    "InvalidProjectNameError",
    "ProjectIdentity",
    "project_package",
    "resolve_project_identity",
    "LLMGenerationReleaseChecklist",
    "run_release_checklist",
    "plan_write",
    "HEALTHY",
    "INCOMPATIBLE",
    "INVALID",
    "LLMGeneratedProjectHealth",
    "check_generated_project",
    "IncompatibleProjectMetadataError",
    "IncompatibleProjectManifestError",
    "README_FILENAME",
    "generate_readme",
    "ENTRYPOINT",
    "MANIFEST_VERSION",
    "PROJECT_MANIFEST_FILENAME",
    "GeneratedProjectManifest",
    "InvalidProjectManifestError",
    "CONTRACT_VERSION",
    "GENERATOR_ID",
    "METADATA_FILENAME",
    "GeneratedProjectMetadata",
    "InvalidProjectMetadataError",
    "COMPLETE",
    "INCOMPLETE",
    "MARKER_FILENAME",
    "UnsafeOutputDirectoryError",
    "generation_status",
    "APIGenerationConfig",
    "STAGES",
    "LLMGeneratedApplication",
    "generate_application",
    "GeneratedArtifactRejectedError",
    "LLMGeneratedArtifactValidation",
    "require_valid",
    "validate_generated_artifact",
    "ASGI_SERVER",
    "InvalidDockerInputError",
    "generate_dockerfile",
    "UnknownGeneratedImportError",
    "generate_requirements",
    "OPENAPI_FILENAME",
    "generated_openapi",
    "write_openapi_contract",
    "UnsafeGeneratedPathError",
    "write_generated_application",
    "FastAPIApplicationGenerator",
    "InvalidDraftEndpointError",
    "APIGenerator",
    "LLMAPIGenerationResult",
    "LLMAPIGenerationService",
    "DraftNotValidatedError",
    "InvalidGeneratorOutputError",
]
