import ast
import re
import sys
from pathlib import Path

# import name -> distribution name. A third-party import that is not listed
# here is an error rather than a guess.
_DISTRIBUTIONS = {"fastapi": "fastapi", "pydantic": "pydantic"}
# Floors for distributions the project's own requirements.txt does not pin.
# pydantic>=2: the generated models use model_dump(), a Pydantic v2 API.
_FALLBACK_SPECIFIERS = {"pydantic": ">=2.0"}
_PROJECT_REQUIREMENTS = Path(__file__).resolve().parents[2] / "requirements.txt"


class UnknownGeneratedImportError(ValueError):
    """Raised when generated code imports a third-party module with no known distribution."""


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _project_specifiers(path) -> dict:
    """{normalised distribution name: specifier} from the project's own
    requirements.txt (its existing version information), or {} if absent."""
    path = Path(path)
    if not path.is_file():
        return {}
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*(.*?)\s*$", line.split("#")[0])
        if match and match.group(1):
            found[_normalise(match.group(1))] = match.group(2)
    return found


def generate_requirements(files: dict, project_requirements=_PROJECT_REQUIREMENTS) -> str:
    """requirements.txt text for exactly the third-party packages the
    generated .py files import -- sorted, one line each, no development or
    test dependencies. Versions come from the project's requirements.txt when
    it pins the package, else from a documented floor, else the bare name."""
    modules = set()
    for path, source in files.items():
        if path.endswith(".py"):
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Import):
                    modules |= {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    modules.add(node.module.split(".")[0])
    third_party = sorted(m for m in modules if m not in sys.stdlib_module_names and m != "app")
    unknown = [m for m in third_party if m not in _DISTRIBUTIONS]
    if unknown:
        raise UnknownGeneratedImportError(f"no known distribution for imports: {unknown}")

    project = _project_specifiers(project_requirements)
    lines = set()
    for module in third_party:
        name = _DISTRIBUTIONS[module]
        specifier = project.get(_normalise(name)) or _FALLBACK_SPECIFIERS.get(name, "")
        lines.add(f"{name}{specifier}")
    return "".join(line + "\n" for line in sorted(lines))
