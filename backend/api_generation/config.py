import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.llm.config import InvalidConfigurationError

from .docker import BASE_IMAGE, DEFAULT_PORT
from .identity import project_package

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
        if not self.output_dir or not isinstance(self.output_dir, (str, Path)) or not str(self.output_dir).strip():
            raise InvalidConfigurationError("output_dir is required")
        if Path(self.output_dir).is_file():
            raise InvalidConfigurationError(f"output_dir {str(self.output_dir)!r} is an existing file")
        if not isinstance(self.base_image, str) or not _IMAGE.match(self.base_image):
            raise InvalidConfigurationError(f"base_image {self.base_image!r} is not a valid image reference")
        if isinstance(self.port, bool) or not isinstance(self.port, int) or not 1 <= self.port <= 65535:
            raise InvalidConfigurationError(f"port {self.port!r} must be an integer from 1 to 65535")
        if self.project_name is not None:
            project_package(self.project_name)  # raises InvalidProjectNameError
        return self
