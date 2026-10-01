import ast
import re
import types
from dataclasses import dataclass

from backend.api_schema_review import APPROVED, REJECTED

from .docker import ASGI_SERVER
from .manifest import UnknownGeneratedImportError, generate_requirements
from .metadata import (
    METADATA_FILENAME,
    GeneratedProjectMetadata,
    IncompatibleProjectMetadataError,
    InvalidProjectMetadataError,
)
from .openapi import OPENAPI_FILENAME, openapi_text
from .project_manifest import (
    PROJECT_MANIFEST_FILENAME,
    GeneratedProjectManifest,
    IncompatibleProjectManifestError,
    InvalidProjectManifestError,
    artifact_type,
)

REQUIRED_FILES = (
    "app/__init__.py", "app/main.py", "requirements.txt", "Dockerfile", METADATA_FILENAME, OPENAPI_FILENAME,
    PROJECT_MANIFEST_FILENAME, "README.md",
)
_DOC_PATHS = frozenset({"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"})


class GeneratedArtifactRejectedError(ValueError):
    """Raised by require_valid() when the generated artifact has blocking findings."""

    def __init__(self, validation):
        super().__init__("; ".join(f"{f['category']}: {f['target']}: {f['message']}" for f in validation.findings))
        self.validation = validation


@dataclass(frozen=True)
class LLMGeneratedArtifactValidation:
    """Outcome of validating a generated project. It follows the existing
    schema-review convention: findings is a list of {"category", "target",
    "message", "blocking"} dicts, and status is APPROVED only when none is
    blocking. Validation is read-only."""

    findings: list
    status: str

    @property
    def valid(self) -> bool:
        return self.status == APPROVED


def _finding(category, target, message):
    return {"category": category, "target": target, "message": message, "blocking": True}


def validate_generated_artifact(files: dict) -> LLMGeneratedArtifactValidation:
    """Check that the generated files are complete and mutually consistent.
    Every independent problem is reported; checks that need a prerequisite
    (importing needs valid syntax, routes need an importable app) are skipped
    when it failed. The generated module is imported in a throwaway module:
    it contains only the generated models and routes, never notebook code."""
    findings = []

    for path in REQUIRED_FILES:
        if path not in files:
            findings.append(_finding("MISSING_FILE", path, "required generated file is absent"))
        elif path != "app/__init__.py" and not files[path].strip():
            findings.append(_finding("EMPTY_FILE", path, "generated file is empty"))

    metadata = None
    if METADATA_FILENAME in files and files[METADATA_FILENAME].strip():
        try:
            metadata = GeneratedProjectMetadata.parse(files[METADATA_FILENAME])
        except IncompatibleProjectMetadataError as error:
            findings.append(_finding("INCOMPATIBLE_PROJECT", METADATA_FILENAME, str(error)))
        except InvalidProjectMetadataError as error:
            findings.append(_finding("INVALID_METADATA", METADATA_FILENAME, str(error)))

    manifest = None
    if PROJECT_MANIFEST_FILENAME in files and files[PROJECT_MANIFEST_FILENAME].strip():
        try:
            manifest = GeneratedProjectManifest.parse(files[PROJECT_MANIFEST_FILENAME])
        except IncompatibleProjectManifestError as error:
            findings.append(_finding("INCOMPATIBLE_PROJECT", PROJECT_MANIFEST_FILENAME, str(error)))
        except InvalidProjectManifestError as error:
            findings.append(_finding("INVALID_MANIFEST", PROJECT_MANIFEST_FILENAME, str(error)))
    if manifest is not None:
        present = tuple(sorted((p, artifact_type(p)) for p in files if artifact_type(p)))
        if manifest.artifacts != present:
            findings.append(_finding("MANIFEST_ARTIFACTS", PROJECT_MANIFEST_FILENAME, "artifact list differs from the generated files"))
        dockerfile_text = files.get("Dockerfile", "")
        if manifest.entrypoint not in dockerfile_text or f"FROM {manifest.base_image}\n" not in dockerfile_text + "\n" \
                or f"PORT={manifest.port}" not in dockerfile_text:
            findings.append(_finding("MANIFEST_CONFIGURATION", PROJECT_MANIFEST_FILENAME, "entrypoint/base image/port do not match the Dockerfile"))
        if metadata is not None and manifest.contract_version != metadata.contract_version:
            findings.append(_finding("MANIFEST_CONFIGURATION", PROJECT_MANIFEST_FILENAME, "contract_version differs from the project metadata"))

    readme = files.get("README.md", "")
    if readme.strip() and manifest is not None:
        missing_mentions = [
            token for token in (manifest.entrypoint, "requirements.txt", "openapi.json", "prereqai-project.json",
                                f"--port {manifest.port}", f"`{manifest.base_image}`")
            if token not in readme
        ]
        if missing_mentions or re.search(r"(^|[\s`(])/(home|tmp|Users|var|root)/", readme):
            findings.append(_finding("README_INCOMPLETE", "README.md",
                                     f"missing {missing_mentions} or contains a machine-specific path"))

    syntax_ok = True
    for path in sorted(files):
        if path.endswith(".py"):
            try:
                ast.parse(files[path], filename=path)
            except SyntaxError as error:
                syntax_ok = False
                findings.append(_finding("SYNTAX_ERROR", path, f"line {error.lineno}: {error.msg}"))

    main = files.get("app/main.py", "")
    app = None
    if syntax_ok and main.strip():
        module = types.ModuleType("validated_generated_app")
        try:
            exec(compile(main, "app/main.py", "exec"), module.__dict__)
        except Exception as error:
            findings.append(_finding("IMPORT_ERROR", "app/main.py", f"{type(error).__name__}: {error}"))
        else:
            app = getattr(module, "app", None)
            if not (hasattr(app, "routes") and hasattr(app, "openapi")):
                findings.append(_finding("NO_ENTRYPOINT", "app/main.py", "module does not define a FastAPI `app`"))
                app = None

    if app is not None:
        routes = [r for r in app.routes if getattr(r, "path", None) not in _DOC_PATHS]
        if not routes:
            findings.append(_finding("NO_ROUTES", "app/main.py", "the generated app registers no endpoints"))
        try:
            document = app.openapi()
        except Exception as error:
            findings.append(_finding("OPENAPI_ERROR", "app/main.py", f"{type(error).__name__}: {error}"))
        else:
            registered = {(r.path, m.lower()) for r in routes for m in getattr(r, "methods", ())}
            documented = {(p, m) for p, item in document.get("paths", {}).items() for m in item}
            if metadata is not None and (metadata.endpoint.split(" ", 1)[-1], metadata.endpoint.split(" ", 1)[0].lower()) not in registered:
                findings.append(_finding("METADATA_MISMATCH", METADATA_FILENAME, "endpoint is not registered by the generated app"))
            if files.get(OPENAPI_FILENAME, "").strip() and files[OPENAPI_FILENAME] != openapi_text(files):
                findings.append(_finding("OPENAPI_FILE_MISMATCH", OPENAPI_FILENAME, "differs from the generated app's own OpenAPI document"))
            if registered != documented:
                findings.append(_finding("OPENAPI_MISMATCH", "openapi", "documented operations differ from registered routes"))

    if "requirements.txt" in files and syntax_ok:
        try:
            expected = generate_requirements(files, also=(ASGI_SERVER,))
        except UnknownGeneratedImportError as error:
            findings.append(_finding("UNKNOWN_DEPENDENCY", "requirements.txt", str(error)))
        else:
            if files["requirements.txt"] != expected:
                findings.append(_finding("MANIFEST_MISMATCH", "requirements.txt", "does not match the generated imports"))

    dockerfile = files.get("Dockerfile", "")
    if dockerfile.strip():
        for source in re.findall(r"^COPY\s+(\S+)\s", dockerfile, flags=re.MULTILINE):
            if not any(p == source or p.startswith(source.rstrip("/") + "/") for p in files):
                findings.append(_finding("DOCKER_COPY_SOURCE", "Dockerfile", f"copies {source!r}, which was not generated"))
        entrypoint = re.search(r"\b([\w.]+):app\b", dockerfile)
        if not entrypoint or entrypoint.group(1).replace(".", "/") + ".py" not in files:
            findings.append(_finding("DOCKER_ENTRYPOINT", "Dockerfile", "start command does not reference a generated module"))
        if "pip install" not in dockerfile or "requirements.txt" not in dockerfile:
            findings.append(_finding("DOCKER_INSTALL", "Dockerfile", "does not install the generated requirements.txt"))

    return LLMGeneratedArtifactValidation(findings=findings, status=REJECTED if findings else APPROVED)


def require_valid(files: dict) -> LLMGeneratedArtifactValidation:
    """validate_generated_artifact(), raising GeneratedArtifactRejectedError
    (carrying every finding) instead of returning a REJECTED result."""
    validation = validate_generated_artifact(files)
    if not validation.valid:
        raise GeneratedArtifactRejectedError(validation)
    return validation
