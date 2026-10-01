import json
from dataclasses import asdict, dataclass

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

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"

    @classmethod
    def parse(cls, text: str) -> "GeneratedProjectMetadata":
        try:
            data = json.loads(text)
            if not isinstance(data, dict) or set(data) != set(cls.__dataclass_fields__):
                raise ValueError("unexpected fields")
            metadata = cls(**data)
        except (ValueError, TypeError) as error:
            raise InvalidProjectMetadataError(f"cannot parse {METADATA_FILENAME}: {error}") from error
        if metadata.generator != GENERATOR_ID or metadata.project_type != PROJECT_TYPE:
            raise IncompatibleProjectMetadataError(f"{METADATA_FILENAME} was not produced by {GENERATOR_ID} ({PROJECT_TYPE})")
        if metadata.contract_version != CONTRACT_VERSION or isinstance(metadata.contract_version, bool):
            raise IncompatibleProjectMetadataError(f"unsupported contract_version {metadata.contract_version!r}")
        for name in ("draft_id", "endpoint"):
            if not isinstance(getattr(metadata, name), str) or not getattr(metadata, name):
                raise InvalidProjectMetadataError(f"{name} must be a non-empty string")
        return metadata
