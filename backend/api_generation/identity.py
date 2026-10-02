import keyword
import re
import sys
from dataclasses import dataclass

from backend.llm.config import InvalidConfigurationError

DEFAULT_PACKAGE = "app"
DEFAULT_IMAGE_NAME = "generated-api"
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_ENTRYPOINT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.main:app$")
# Packages a generated project imports or runs; a project package with one of
# these names would shadow it and break the app at import time.
_RESERVED_PACKAGES = frozenset({"fastapi", "pydantic", "starlette", "uvicorn", "typing_extensions", "anyio"})


class InvalidProjectNameError(InvalidConfigurationError):
    """Raised when an explicit project name cannot become a valid, importable
    Python package for the generated project."""


@dataclass(frozen=True)
class ProjectIdentity:
    """The one resolved identity of a generated project. `name` is what the
    manifest, metadata, README title and FastAPI title show; `package` is the
    generated Python package the application lives in. Everything else
    (module path, entrypoint, Docker image tag) is derived from those two, so
    no generated artifact can disagree with another about them."""

    name: str
    package: str = DEFAULT_PACKAGE
    explicit: bool = False

    @property
    def main_path(self) -> str:
        return f"{self.package}/main.py"

    @property
    def init_path(self) -> str:
        return f"{self.package}/__init__.py"

    @property
    def entrypoint(self) -> str:
        return f"{self.package}.main:app"

    @property
    def image_name(self) -> str:
        return self.package.replace("_", "-") if self.explicit else DEFAULT_IMAGE_NAME


def project_package(name) -> str:
    """The Python package an explicit project name generates: lower-cased,
    with hyphens turned into underscores ("Loan-Quote" -> "loan_quote").
    Names that cannot be normalized into a safe, importable package are
    rejected rather than producing a project that fails at import time."""
    if not isinstance(name, str) or not _NAME.match(name):
        raise InvalidProjectNameError(
            f"project_name {name!r} must start with a letter and contain only letters, digits, '-' and '_' "
            "(at most 64 characters)"
        )
    package = name.lower().replace("-", "_")
    if keyword.iskeyword(package) or keyword.issoftkeyword(package):
        raise InvalidProjectNameError(f"project_name {name!r} becomes the Python keyword {package!r}")
    if package in _RESERVED_PACKAGES or package in sys.stdlib_module_names:
        raise InvalidProjectNameError(f"project_name {name!r} becomes package {package!r}, which would shadow a module the app imports")
    return package


def resolve_project_identity(draft, project_name=None) -> ProjectIdentity:
    """Precedence follows APIGenerationConfig's convention: an explicit
    project_name, then the default. The default reproduces the previous
    output exactly: the draft's summary as the name and the `app` package."""
    if project_name is None:
        return ProjectIdentity(draft.summary)
    return ProjectIdentity(project_name, project_package(project_name), explicit=True)


def package_from_entrypoint(entrypoint):
    """The package named by a `<package>.main:app` entrypoint, or None."""
    match = _ENTRYPOINT.match(entrypoint) if isinstance(entrypoint, str) else None
    return match.group(1) if match else None


_MAIN_MODULE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*/main\.py$")


def main_module_path(files) -> str:
    """The generated application module among `files`: the default
    `app/main.py` when present, otherwise the one `<package>/main.py`."""
    if f"{DEFAULT_PACKAGE}/main.py" in files:
        return f"{DEFAULT_PACKAGE}/main.py"
    candidates = sorted(p for p in files if _MAIN_MODULE.match(p))
    return candidates[0] if candidates else f"{DEFAULT_PACKAGE}/main.py"
