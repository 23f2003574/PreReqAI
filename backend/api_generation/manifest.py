import ast
import re
import sys
from pathlib import Path

# import name -> distribution name. A third-party import that is not listed
# here is an error rather than a guess.
_DISTRIBUTIONS = {"fastapi": "fastapi", "pydantic": "pydantic"}
# The generated project's own minimum versions. They are fixed here, as part
# of the generated-project contract, rather than read from PreReqAI's own
# development requirements.txt: a generated project must not change (or stop
# validating) because the generator's development environment did.
# fastapi>=0.115 / uvicorn>=0.32: the versions the generated app and its start
# command are developed and tested against; pydantic>=2: the generated models
# use model_dump(), a Pydantic v2 API.
GENERATED_SPECIFIERS = {"fastapi": ">=0.115.0", "pydantic": ">=2.0", "uvicorn": ">=0.32.0"}


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


def generate_requirements(files: dict, project_requirements=None, also=()) -> str:
    """requirements.txt text for exactly the third-party packages the
    generated .py files import -- sorted, one line each, no development or
    test dependencies. Versions come from GENERATED_SPECIFIERS (self-contained;
    nothing from the host environment is read), or -- only when a caller
    passes one explicitly -- from the given `project_requirements` file.
    `also` names distributions the artifact needs without importing them
    (the ASGI server its start command runs)."""
    modules = set()
    for path, source in files.items():
        if path.endswith(".py"):
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Import):
                    modules |= {alias.name.split(".")[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    modules.add(node.module.split(".")[0])
    own_packages = {path.split("/")[0] for path in files if "/" in path}  # the generated package itself
    third_party = sorted(m for m in modules if m not in sys.stdlib_module_names and m not in own_packages)
    unknown = [m for m in third_party if m not in _DISTRIBUTIONS]
    if unknown:
        raise UnknownGeneratedImportError(f"no known distribution for imports: {unknown}")

    project = _project_specifiers(project_requirements) if project_requirements is not None else {}
    lines = set()
    for name in [_DISTRIBUTIONS[m] for m in third_party] + list(also):
        specifier = project.get(_normalise(name)) or GENERATED_SPECIFIERS.get(name, "")
        lines.add(f"{name}{specifier}")
    return "".join(line + "\n" for line in sorted(lines))
