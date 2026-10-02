import json
import shlex
from dataclasses import asdict, dataclass
from pathlib import Path

from .metadata import METADATA_FILENAME
from .project_manifest import PROJECT_MANIFEST_FILENAME, artifact_type
from .config import CONFIG_FILENAME
from .validation import UNKNOWN, diagnose_compatibility, validate_generated_artifact
from .writer import INCOMPLETE, MARKER_FILENAME, generation_status

HEALTHY = "healthy"
INVALID = "invalid"
INCOMPATIBLE = "incompatible"

# check name -> (finding categories, or targets) that make it fail
_CHECKS = (
    ("manifest", {"INVALID_MANIFEST", "MANIFEST_ARTIFACTS", "MANIFEST_CONFIGURATION", "IDENTITY_MISMATCH", "INVALID_CONFIG", "CONFIG_MISMATCH"}, {PROJECT_MANIFEST_FILENAME}),
    ("metadata", {"INVALID_METADATA", "METADATA_MISMATCH"}, {METADATA_FILENAME}),
    ("entrypoint", {"NO_ENTRYPOINT", "NO_ROUTES"}, {"app/main.py", "app/__init__.py"}),
    ("python", {"SYNTAX_ERROR", "IMPORT_ERROR"}, set()),
    ("dependencies", {"MANIFEST_MISMATCH", "UNKNOWN_DEPENDENCY"}, {"requirements.txt"}),
    ("openapi", {"OPENAPI_ERROR", "OPENAPI_MISMATCH", "OPENAPI_FILE_MISMATCH"}, {"openapi.json"}),
)


@dataclass(frozen=True)
class LLMGeneratedProjectHealth:
    """Result of check_generated_project(). status is healthy, invalid or
    incompatible (a manifest/metadata from another generator or contract
    version); findings use the generated-artifact validation convention
    ({"category", "target", "message", "blocking"}); checks maps each named
    check to "passed" or "failed"."""

    status: str
    checks: dict
    findings: list
    compatibility: dict = None  # validation.diagnose_compatibility() of the project

    @property
    def healthy(self) -> bool:
        return self.status == HEALTHY

    def to_dict(self) -> dict:
        return asdict(self)


def _read_project(root: Path) -> dict:
    files = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file() and "__pycache__" not in path.parts and relative != MARKER_FILENAME \
                and (artifact_type(relative) or relative.endswith(".py") or relative == PROJECT_MANIFEST_FILENAME):
            files[relative] = path.read_text(encoding="utf-8", errors="replace")
    return files


def regeneration_guidance(compatibility: dict, project_dir, files: dict):
    """Informational guidance for an *upgradable* project (older but still
    compatible): which versions it records against the generator's current
    ones, and the real `api-generation generate` command that regenerates it
    in place with its own prereqai-config.json (so its project name, base
    image and port are kept). None for every other state: current projects
    need nothing, and incompatible ones get the stronger compatibility
    remediation instead. Nothing is run or changed here."""
    if compatibility["status"] != "upgradable":
        return None
    try:
        draft_id = json.loads(files[METADATA_FILENAME])["draft_id"]
    except (KeyError, TypeError, ValueError):
        draft_id = None
    root = str(Path(project_dir).resolve())
    command = ["python", "-m", "backend.cli", "api-generation", "generate",
               "--draft", "<validated-draft.json>", "--output-dir", root]
    if CONFIG_FILENAME in files:
        command += ["--config", str(Path(root) / CONFIG_FILENAME)]
    return {
        "versions": [{"file": i["file"], "field": i["field"], "project": i["found"], "generator": i["supported"]}
                     for i in compatibility["issues"]],
        "draft_id": draft_id,
        "command": " ".join(part if part.startswith("<") else shlex.quote(part) for part in command),
        "note": (f"<validated-draft.json> is the validated draft '{draft_id}' this project was generated from. "
                 "Regeneration is optional and only happens when you run the command."),
    }


def check_generated_project(output_dir) -> LLMGeneratedProjectHealth:
    """Read-only health check of a generated project on disk. It reads the
    project's files and runs the existing generated-artifact validation on
    them (syntax, import of the generated app, routes, OpenAPI, manifest,
    metadata, dependencies, Dockerfile, README) -- no check is duplicated
    here. Nothing is installed or launched, and no notebook code exists in a
    generated project to run."""
    root = Path(output_dir)
    if not root.is_dir():
        findings = [{"category": "NOT_A_PROJECT", "target": str(output_dir), "message": "not a directory", "blocking": True}]
        compatibility = {**diagnose_compatibility({}), "status": UNKNOWN, "regeneration": None,
                         "remediation": f"{output_dir} is not a directory; pass the generated project directory."}
        return LLMGeneratedProjectHealth(INVALID, {name: "failed" for name, _, _ in _CHECKS}, findings, compatibility)

    files = _read_project(root)
    findings = list(validate_generated_artifact(files).findings)
    if generation_status(root) == INCOMPLETE:
        findings.append({"category": "INCOMPLETE_GENERATION", "target": MARKER_FILENAME, "blocking": True,
                         "message": "the last generation run did not finish; regenerate this project"})
    checks = {}
    for name, categories, targets in _CHECKS:
        failed = any(f["category"] in categories or (f["category"] in {"MISSING_FILE", "EMPTY_FILE", "INCOMPATIBLE_PROJECT"}
                                                      and f["target"] in targets) for f in findings)
        checks[name] = "failed" if failed else "passed"
    if any(f["category"] == "INCOMPATIBLE_PROJECT" for f in findings):
        status = INCOMPATIBLE
    else:
        status = INVALID if findings else HEALTHY
    compatibility = diagnose_compatibility(files)
    compatibility["regeneration"] = regeneration_guidance(compatibility, root, files)
    return LLMGeneratedProjectHealth(status, checks, findings, compatibility)
