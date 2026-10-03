import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.llm.config import InvalidConfigurationError

from .docker import BASE_IMAGE, DEFAULT_PORT
from .identity import project_package
from .metadata import require_version

class IncompatibleConfigurationError(InvalidConfigurationError):
    """prereqai-config.json is from another config_version (see
    metadata.version_compatibility); `.compatibility` holds the details."""


CONFIG_FILENAME = "prereqai-config.json"
CONFIG_VERSION = 1
# prereqai-config.json keeps the two kinds of setting apart: "generation" is
# read only by the generator (how it names the project), "runtime" describes
# how the generated project is built and served (its Docker base image and
# default port, which the HOST/PORT environment variables of the generated
# Dockerfile override at run time). output_dir is machine-specific and the
# generator's own development settings never belong to a generated project,
# so neither is stored.
_SECTIONS = {"generation": ("project_name",), "runtime": ("base_image", "port")}
_FILE_FIELDS = tuple(name for names in _SECTIONS.values() for name in names)
_IMAGE = re.compile(r"^[a-z0-9][a-z0-9._/-]*(:[A-Za-z0-9._-]+)?(@sha256:[0-9a-f]{64})?$")


@dataclass
class APIGenerationConfig:
    """Configuration for one generation run, following the repository's
    existing configuration convention (a dataclass whose validate() raises
    InvalidConfigurationError, as LLMProviderConfig does). It covers only
    what the generator really varies: where the project is written and the
    two Dockerfile values that used to be hard-coded, plus the project name
    (see identity.resolve_project_identity). Defaults reproduce the
    previous behaviour exactly. There is no config file or environment
    layer in this repository, so precedence is: explicit value, then default."""

    output_dir: str
    base_image: str = BASE_IMAGE
    port: int = DEFAULT_PORT
    project_name: Optional[str] = None

    def validate(self):
        """Check every setting and report all the invalid ones together. A
        single problem raises its own error (e.g. InvalidProjectNameError);
        several raise one InvalidConfigurationError listing each."""
        problems = []
        if not self.output_dir or not isinstance(self.output_dir, (str, Path)) or not str(self.output_dir).strip():
            problems.append(InvalidConfigurationError("output_dir is required"))
        elif Path(self.output_dir).is_file():
            problems.append(InvalidConfigurationError(f"output_dir {str(self.output_dir)!r} is an existing file"))
        if not isinstance(self.base_image, str) or not _IMAGE.match(self.base_image):
            problems.append(InvalidConfigurationError(f"base_image {self.base_image!r} is not a valid image reference"))
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            problems.append(InvalidConfigurationError(f"port {self.port!r} must be an integer from 1 to 65535"))
        if self.project_name is not None:
            try:
                project_package(self.project_name)
            except InvalidConfigurationError as error:
                problems.append(error)
        if len(problems) == 1:
            raise problems[0]
        if problems:
            raise InvalidConfigurationError("; ".join(str(problem) for problem in problems))
        return self

    def to_file_dict(self) -> dict:
        """The settings a generated project's prereqai-config.json records,
        split into "generation" and "runtime" sections, defaults written out."""
        return {"config_version": CONFIG_VERSION,
                **{section: {name: getattr(self, name) for name in names} for section, names in _SECTIONS.items()}}

    @classmethod
    def from_file_text(cls, text: str, output_dir, overrides: dict = None) -> "APIGenerationConfig":
        """Parse a prereqai-config.json and validate it with validate().
        Every setting must be present and nothing else may be: a typo or a
        missing key is an error, never a silent fallback to a default.
        `overrides` (explicit values, e.g. CLI flags) take precedence."""
        try:
            data = json.loads(text)
        except ValueError as error:
            raise InvalidConfigurationError(f"{CONFIG_FILENAME} is not valid JSON: {error}") from error
        if isinstance(data, dict) and set(_SECTIONS) & set(data):
            require_version(data, "config_version", CONFIG_VERSION, CONFIG_FILENAME, IncompatibleConfigurationError)
        expected = {"config_version", *_SECTIONS}
        if not isinstance(data, dict) or set(data) != expected:
            keys = sorted(data) if isinstance(data, dict) else type(data).__name__
            raise InvalidConfigurationError(f"{CONFIG_FILENAME} must contain exactly {sorted(expected)}, got {keys}")
        values = {}
        for section, names in _SECTIONS.items():
            settings = data[section]
            if not isinstance(settings, dict) or set(settings) != set(names):
                keys = sorted(settings) if isinstance(settings, dict) else type(settings).__name__
                raise InvalidConfigurationError(f"{CONFIG_FILENAME} section {section!r} must contain exactly {sorted(names)}, got {keys}")
            values.update(settings)
        if values["project_name"] is not None and not isinstance(values["project_name"], str):
            raise InvalidConfigurationError(f"project_name {values['project_name']!r} must be a string or null")
        values.update(overrides or {})
        return cls(output_dir=output_dir, **values).validate()

    @classmethod
    def from_file(cls, path, output_dir, overrides: dict = None) -> "APIGenerationConfig":
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as error:
            raise InvalidConfigurationError(f"cannot read {path}: {error.strerror}") from error
        return cls.from_file_text(text, output_dir, overrides)


def config_file_text(base_image: str, port: int, project_name=None) -> str:
    """Deterministic text of a generated project's prereqai-config.json."""
    config = APIGenerationConfig(output_dir=".", base_image=base_image, port=port, project_name=project_name)
    return json.dumps(config.to_file_dict(), indent=2, sort_keys=True) + "\n"
