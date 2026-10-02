import json
import re
from dataclasses import dataclass

from .metadata import CONTRACT_VERSION, METADATA_FILENAME

PROJECT_MANIFEST_FILENAME = "prereqai-manifest.json"
MANIFEST_VERSION = 1
ENTRYPOINT = "app.main:app"
OPENAPI_FILENAME = "openapi.json"


_PACKAGE_SOURCE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*/[^/]+\.py$")  # a file of the generated package


class InvalidProjectManifestError(ValueError):
    """Raised when a generated project's manifest is malformed or not for this generator contract."""


def artifact_type(path: str):
    """The artifact type of a generated file, or None if it has no type."""
    if _PACKAGE_SOURCE.match(path):
        return "application-source"
    return {
        "requirements.txt": "dependency-manifest",
        "Dockerfile": "container-image",
        METADATA_FILENAME: "project-metadata",
        OPENAPI_FILENAME: "openapi-contract",
        "README.md": "documentation",
    }.get(path)


class IncompatibleProjectManifestError(InvalidProjectManifestError):
    """The manifest is well formed but belongs to another manifest or contract version."""


@dataclass(frozen=True)
class GeneratedProjectManifest:
    """Machine-readable inventory of a generated project: the application it
    contains, its entrypoint, every generated artifact with its type, and the
    configuration that affects reproducibility. Identity (draft, endpoint,
    generator) lives in prereqai-project.json, which this file points to, not
    copies. It holds only relative paths and no timestamps, environment or
    machine-specific data, so the same input and configuration always yield
    the same bytes."""

    application_name: str
    artifacts: tuple  # ((relative path, artifact type), ...) sorted by path
    base_image: str
    port: int
    entrypoint: str = ENTRYPOINT
    metadata_file: str = METADATA_FILENAME
    contract_version: int = CONTRACT_VERSION
    manifest_version: int = MANIFEST_VERSION

    @classmethod
    def for_files(cls, files: dict, application_name: str, base_image: str, port: int, entrypoint: str = ENTRYPOINT):
        artifacts = tuple(sorted((p, artifact_type(p)) for p in files if artifact_type(p)))
        return cls(application_name, artifacts, base_image, port, entrypoint)

    def to_dict(self) -> dict:
        return {
            "manifest_version": self.manifest_version, "contract_version": self.contract_version,
            "metadata_file": self.metadata_file,
            "application": {"name": self.application_name, "entrypoint": self.entrypoint},
            "artifacts": [{"path": p, "type": t} for p, t in self.artifacts],
            "configuration": {"base_image": self.base_image, "port": self.port},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    @classmethod
    def parse(cls, text: str) -> "GeneratedProjectManifest":
        try:
            data = json.loads(text)
            if set(data) != {"manifest_version", "contract_version", "metadata_file", "application", "artifacts", "configuration"}:
                raise ValueError("unexpected top-level fields")
            if set(data["application"]) != {"name", "entrypoint"} or set(data["configuration"]) != {"base_image", "port"}:
                raise ValueError("unexpected nested fields")
            artifacts = tuple((a["path"], a["type"]) for a in data["artifacts"])
            manifest = cls(
                data["application"]["name"], artifacts, data["configuration"]["base_image"],
                data["configuration"]["port"], data["application"]["entrypoint"], data["metadata_file"],
                data["contract_version"], data["manifest_version"],
            )
        except (ValueError, TypeError, KeyError) as error:
            raise InvalidProjectManifestError(f"cannot parse {PROJECT_MANIFEST_FILENAME}: {error}") from error
        for flag, value in (("manifest_version", MANIFEST_VERSION), ("contract_version", CONTRACT_VERSION)):
            actual = getattr(manifest, flag)
            if actual != value or isinstance(actual, bool):
                raise IncompatibleProjectManifestError(f"unsupported {flag} {actual!r}")
        from .identity import package_from_entrypoint
        if manifest.metadata_file != METADATA_FILENAME or package_from_entrypoint(manifest.entrypoint) is None:
            raise InvalidProjectManifestError("metadata_file/entrypoint do not match this generator's contract")
        if not isinstance(manifest.application_name, str) or not manifest.application_name:
            raise InvalidProjectManifestError("application.name must be a non-empty string")
        for path, kind in artifacts:
            if not isinstance(path, str) or path.startswith("/") or ".." in path.split("/") or artifact_type(path) != kind:
                raise InvalidProjectManifestError(f"invalid artifact entry {path!r}: {kind!r}")
        if list(artifacts) != sorted(set(artifacts)):
            raise InvalidProjectManifestError("artifacts must be sorted and unique")
        return manifest
