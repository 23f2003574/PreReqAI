import json
from dataclasses import asdict, dataclass
from typing import Optional

METADATA_FILENAME = "prereqai-project.json"
GENERATOR_ID = "prereqai.api_generation"
CONTRACT_VERSION = 1
PROJECT_TYPE = "fastapi-app"


class InvalidProjectMetadataError(ValueError):
    """Raised when a generated project's metadata file is malformed or does
    not belong to this generator and contract version."""


class IncompatibleProjectMetadataError(InvalidProjectMetadataError):
    """The metadata is well formed but was produced by another generator or contract version."""


@dataclass(frozen=True)
class GeneratedProjectMetadata:
    """Identity of a generated project: which generator and contract produced
    it, what kind of project it is, and the documentation draft and endpoint
    it came from. It deliberately has no timestamp, so identical input always
    produces an identical file."""

    draft_id: str
    endpoint: str
    generator: str = GENERATOR_ID
    contract_version: int = CONTRACT_VERSION
    project_type: str = PROJECT_TYPE
    # An explicitly configured project name; absent (and omitted from the
    # file) for the default identity, so existing projects parse unchanged.
    project_name: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        if data["project_name"] is None:
            del data["project_name"]
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    @classmethod
    def parse(cls, text: str) -> "GeneratedProjectMetadata":
        try:
            data = json.loads(text)
            if not isinstance(data, dict) or set(data) - {"project_name"} != set(cls.__dataclass_fields__) - {"project_name"}:
                raise ValueError("unexpected fields")
            metadata = cls(**data)
        except (ValueError, TypeError) as error:
            raise InvalidProjectMetadataError(f"cannot parse {METADATA_FILENAME}: {error}") from error
        if metadata.generator != GENERATOR_ID or metadata.project_type != PROJECT_TYPE:
            raise IncompatibleProjectMetadataError(f"{METADATA_FILENAME} was not produced by {GENERATOR_ID} ({PROJECT_TYPE})")
        if metadata.contract_version != CONTRACT_VERSION or isinstance(metadata.contract_version, bool):
            raise IncompatibleProjectMetadataError(f"unsupported contract_version {metadata.contract_version!r}")
        if metadata.project_name is not None:
            from .identity import InvalidProjectNameError, project_package
            try:
                project_package(metadata.project_name)
            except InvalidProjectNameError as error:
                raise InvalidProjectMetadataError(str(error)) from error
        for name in ("draft_id", "endpoint"):
            if not isinstance(getattr(metadata, name), str) or not getattr(metadata, name):
                raise InvalidProjectMetadataError(f"{name} must be a non-empty string")
        return metadata
