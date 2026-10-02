import ast
import re
import types
from dataclasses import dataclass

from backend.api_schema_review import APPROVED, REJECTED

from backend.llm.config import InvalidConfigurationError

import json

from .config import CONFIG_FILENAME, CONFIG_VERSION, APIGenerationConfig, IncompatibleConfigurationError
from .docker import ASGI_SERVER
from .identity import (
    DEFAULT_PACKAGE,
    InvalidProjectNameError,
    main_module_path,
    package_from_entrypoint,
    project_package,
)
from .manifest import UnknownGeneratedImportError, generate_requirements
from .metadata import (
    CONTRACT_VERSION,
    GENERATOR_ID,
    NEWER,
    OLDEST_COMPATIBLE,
    UPGRADABLE,
    METADATA_FILENAME,
    version_compatibility,
    GeneratedProjectMetadata,
    IncompatibleProjectMetadataError,
    InvalidProjectMetadataError,
)
from .openapi import OPENAPI_FILENAME, format_openapi
from .project_manifest import (
    MANIFEST_VERSION,
    PROJECT_MANIFEST_FILENAME,
    GeneratedProjectManifest,
    IncompatibleProjectManifestError,
    InvalidProjectManifestError,
    artifact_type,
)

REQUIRED_FILES = (  # for the default `app` package; see _required_files
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


def _required_files(package: str) -> tuple:
    return (f"{package}/__init__.py", f"{package}/main.py") + REQUIRED_FILES[2:]


def _finding(category, target, message):
    return {"category": category, "target": target, "message": message, "blocking": True}


def _incompatible(target, error):
    """An INCOMPATIBLE_PROJECT finding; `details` carries the structured
    version comparison (file, field, found, supported, relation) when the
    cause is a contract/manifest/config version rather than another generator."""
    finding = _finding("INCOMPATIBLE_PROJECT", target, str(error))
    if getattr(error, "compatibility", None):
        finding["details"] = error.compatibility
    return finding


def validate_generated_artifact(files: dict) -> LLMGeneratedArtifactValidation:
    """Check that the generated files are complete and mutually consistent.
    Every independent problem is reported; checks that need a prerequisite
    (importing needs valid syntax, routes need an importable app) are skipped
    when it failed. The generated module is imported in a throwaway module:
    it contains only the generated models and routes, never notebook code."""
    findings = []
    main_path = main_module_path(files)
    package = main_path.split("/")[0]

    for path in _required_files(package):
        if path not in files:
            findings.append(_finding("MISSING_FILE", path, "required generated file is absent"))
        elif path != f"{package}/__init__.py" and not files[path].strip():
            findings.append(_finding("EMPTY_FILE", path, "generated file is empty"))

    metadata = None
    if METADATA_FILENAME in files and files[METADATA_FILENAME].strip():
        try:
            metadata = GeneratedProjectMetadata.parse(files[METADATA_FILENAME])
        except IncompatibleProjectMetadataError as error:
            findings.append(_incompatible(METADATA_FILENAME, error))
        except InvalidProjectMetadataError as error:
            findings.append(_finding("INVALID_METADATA", METADATA_FILENAME, str(error)))

    manifest = None
    if PROJECT_MANIFEST_FILENAME in files and files[PROJECT_MANIFEST_FILENAME].strip():
        try:
            manifest = GeneratedProjectManifest.parse(files[PROJECT_MANIFEST_FILENAME])
        except IncompatibleProjectManifestError as error:
            findings.append(_incompatible(PROJECT_MANIFEST_FILENAME, error))
        except InvalidProjectManifestError as error:
            findings.append(_finding("INVALID_MANIFEST", PROJECT_MANIFEST_FILENAME, str(error)))
    if CONFIG_FILENAME in files:
        try:
            APIGenerationConfig.from_file_text(files[CONFIG_FILENAME], ".")
        except IncompatibleConfigurationError as error:
            findings.append(_incompatible(CONFIG_FILENAME, error))
        except InvalidConfigurationError:
            pass  # reported with the manifest comparison below
    if any(f["category"] == "INCOMPATIBLE_PROJECT" for f in findings):
        # A project from another contract is never imported or executed: its
        # code and layout belong to a contract this validator does not know,
        # so later checks would only fail obscurely.
        return LLMGeneratedArtifactValidation(findings=findings, status=REJECTED)

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
        # One identity everywhere: the manifest's entrypoint names the
        # package that holds the app, and an explicitly named project carries
        # the same name (and the package derived from it) in both files.
        manifest_package = package_from_entrypoint(manifest.entrypoint)
        expected_package = DEFAULT_PACKAGE
        if metadata is not None and metadata.project_name is not None:
            try:
                expected_package = project_package(metadata.project_name)
            except InvalidProjectNameError:
                expected_package = None
        if CONFIG_FILENAME in files:
            # The editable prereqai-config.json must describe this project:
            # the same base image and port as the manifest/Dockerfile and the
            # same explicit project name (or none) as the metadata.
            try:
                config = APIGenerationConfig.from_file_text(files[CONFIG_FILENAME], ".")
            except InvalidConfigurationError as error:
                findings.append(_finding("INVALID_CONFIG", CONFIG_FILENAME, str(error)))
            else:
                project_name = metadata.project_name if metadata is not None else config.project_name
                if (config.base_image, config.port, config.project_name) != (manifest.base_image, manifest.port, project_name):
                    findings.append(_finding("CONFIG_MISMATCH", CONFIG_FILENAME,
                                             "base_image/port/project_name differ from the generated project"))
        if manifest_package != package or (metadata is not None and (
                manifest_package != expected_package
                or (metadata.project_name is not None and manifest.application_name != metadata.project_name))):
            findings.append(_finding("IDENTITY_MISMATCH", PROJECT_MANIFEST_FILENAME,
                                     "project name, package and entrypoint disagree across the generated files"))

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

    main = files.get(main_path, "")
    app = None
    if syntax_ok and main.strip():
        module = types.ModuleType("validated_generated_app")
        try:
            exec(compile(main, main_path, "exec"), module.__dict__)
        except Exception as error:
            findings.append(_finding("IMPORT_ERROR", main_path, f"{type(error).__name__}: {error}"))
        else:
            app = getattr(module, "app", None)
            if not (hasattr(app, "routes") and hasattr(app, "openapi")):
                findings.append(_finding("NO_ENTRYPOINT", main_path, "module does not define a FastAPI `app`"))
                app = None

    if app is not None:
        routes = [r for r in app.routes if getattr(r, "path", None) not in _DOC_PATHS]
        if not routes:
            findings.append(_finding("NO_ROUTES", main_path, "the generated app registers no endpoints"))
        try:
            document = app.openapi()
        except Exception as error:
            findings.append(_finding("OPENAPI_ERROR", main_path, f"{type(error).__name__}: {error}"))
        else:
            registered = {(r.path, m.lower()) for r in routes for m in getattr(r, "methods", ())}
            documented = {(p, m) for p, item in document.get("paths", {}).items() for m in item}
            if metadata is not None and (metadata.endpoint.split(" ", 1)[-1], metadata.endpoint.split(" ", 1)[0].lower()) not in registered:
                findings.append(_finding("METADATA_MISMATCH", METADATA_FILENAME, "endpoint is not registered by the generated app"))
            if files.get(OPENAPI_FILENAME, "").strip() and files[OPENAPI_FILENAME] != format_openapi(document):
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


COMPATIBLE, INCOMPATIBLE_STATUS, UNKNOWN = "compatible", "incompatible", "unknown"
# file -> {version field: version this generator supports}
SUPPORTED_VERSIONS = {
    METADATA_FILENAME: {"contract_version": CONTRACT_VERSION},
    PROJECT_MANIFEST_FILENAME: {"manifest_version": MANIFEST_VERSION, "contract_version": CONTRACT_VERSION},
    CONFIG_FILENAME: {"config_version": CONFIG_VERSION},
}
_REGENERATE = ("Regenerate it with this PreReqAI: python -m backend.cli api-generation generate "
               "--draft <draft.json> --output-dir <project>")


def diagnose_compatibility(files: dict) -> dict:
    """An actionable summary of whether a generated project matches this
    generator's contract, built from the same version rule the validator
    uses (metadata.version_compatibility) -- nothing is parsed twice for a
    different answer. Stable, JSON-ready shape:

      status       compatible (current) | upgradable (an older version that
                   is still compatible: healthy, but regeneration may be
                   required) | incompatible | unknown (a versioned file is
                   missing or is not JSON, so its version cannot be read)
      detected     {file: {field: version found, or None}}
      supported    {file: {field: current version}}
      oldest_compatible  {file: {field: oldest version still accepted}}
                   (versions in between are upgradable; there are no migrations)
      issues       [{"file", "field", "found", "supported", "relation"}],
                   relation upgradable | older | newer | missing | unreadable |
                   other-generator; or {"file", "relation": "absent" |
                   "malformed"} for a file whose version cannot be read
      remediation  one sentence on what to do, or None when compatible
    """
    detected, issues = {}, []
    for file, fields in SUPPORTED_VERSIONS.items():
        text = files.get(file)
        try:
            data = json.loads(text) if text is not None else None
        except ValueError:
            data = None
        if not isinstance(data, dict):
            # the config file is optional for projects generated before it existed
            if not (file == CONFIG_FILENAME and text is None):
                issues.append({"file": file, "relation": "absent" if text is None else "malformed"})
            detected[file] = {field: None for field in fields}
            continue
        detected[file] = {field: data.get(field) for field in fields}
        if file == METADATA_FILENAME and data.get("generator") != GENERATOR_ID:
            issues.append({"file": file, "field": "generator", "found": data.get("generator"),
                           "supported": GENERATOR_ID, "relation": "other-generator"})
            continue
        for field, supported in fields.items():
            details = version_compatibility(data, field, supported, file)
            if details is not None:
                issues.append(details)

    relations = {issue["relation"] for issue in issues}
    if relations & {"older", "newer", "missing", "unreadable", "other-generator"}:
        status = INCOMPATIBLE_STATUS
    elif issues and relations == {UPGRADABLE}:
        status = UPGRADABLE
    else:
        status = UNKNOWN if issues else COMPATIBLE
    if status == COMPATIBLE:
        remediation = None
    elif status == UPGRADABLE:
        fields = ", ".join(f"{i['file']} {i['field']} {i['found']} (current {i['supported']})" for i in issues)
        remediation = ("This project uses an older but still compatible contract: " + fields + ". "
                       "Nothing was changed; regeneration may be required to pick up the current contract. " + _REGENERATE)
    elif NEWER in relations:
        newest = max(i["found"] for i in issues if i["relation"] == NEWER)
        remediation = (f"This project was generated by a newer PreReqAI (a version field records {newest}); "
                       "open or check it with that version, or regenerate it with this one.")
    elif "other-generator" in relations:
        remediation = f"This directory was not generated by {GENERATOR_ID}. " + _REGENERATE
    elif status == INCOMPATIBLE_STATUS:
        remediation = "This project uses an older or unrecorded project contract. " + _REGENERATE
    else:
        remediation = "A versioned project file is missing or is not valid JSON, so compatibility cannot be determined. " + _REGENERATE
    return {"status": status, "detected": detected,
            "supported": {f: dict(v) for f, v in SUPPORTED_VERSIONS.items()},
            "oldest_compatible": {f: {field: OLDEST_COMPATIBLE.get(field, v) for field, v in fields.items()}
                                  for f, fields in SUPPORTED_VERSIONS.items()},
            "issues": issues, "remediation": remediation}
