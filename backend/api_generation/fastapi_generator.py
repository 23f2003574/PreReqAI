import json
import keyword
import re

from backend.api_documentation_draft import LLMAPIDocumentationDraft
from backend.input_schema import ALLOWED_TYPES

from .generator import APIGenerator
from .docker import ASGI_SERVER, generate_dockerfile
from .manifest import generate_requirements

_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
_QUERY_METHODS = frozenset({"GET", "DELETE"})
_PYTHON_TYPES = {
    "int": "int", "float": "float", "str": "str", "bool": "bool",
    "list": "list", "dict": "dict", "tuple": "tuple",
}
assert set(_PYTHON_TYPES) == set(ALLOWED_TYPES)  # stays in step with the schema services' own type set


class InvalidDraftEndpointError(ValueError):
    """Raised when a validated draft's endpoint or field names cannot become
    valid FastAPI code (an unsupported method, a path not starting with '/',
    or a field name that is not a Python identifier)."""


_CONSTRAINT_KEYS = {"min": "ge", "max": "le"}


def _field_name(name: str) -> str:
    if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name):
        raise InvalidDraftEndpointError(f"field name {name!r} is not a valid Python identifier")
    return name


def _base_type(name, entry: dict) -> str:
    type_name = entry.get("type")
    if type_name not in _PYTHON_TYPES:
        raise InvalidDraftEndpointError(f"field {name!r} has type {type_name!r}, which has no safe Python mapping")
    return _PYTHON_TYPES[type_name]


def _model_prefix(method: str, path: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", path)
    return method.capitalize() + "".join(w.capitalize() for w in words)


class _Models:
    """Collects the Pydantic model classes one draft needs, with unique,
    deterministic names derived from the endpoint (nested object structures
    become nested models named after their parent and field)."""

    def __init__(self):
        self.classes = []  # source blocks, dependencies first
        self.names = set()

    def unique(self, name: str) -> str:
        if name in self.names:
            raise InvalidDraftEndpointError(f"generated model name {name!r} would collide")
        self.names.add(name)
        return name

    def annotation(self, owner: str, name: str, entry: dict) -> str:
        base = _base_type(name, entry)
        structure = entry.get("structure") or {}
        if not structure:
            return base
        kind = structure.get("type")
        if kind == "list" and base == "list" and set(structure) == {"type", "items"} and structure["items"] in _PYTHON_TYPES:
            return f"list[{_PYTHON_TYPES[structure['items']]}]"
        props = structure.get("properties")
        if kind == "object" and base == "dict" and set(structure) == {"type", "properties"} and isinstance(props, dict):
            nested = self.unique(owner + name.capitalize())
            body = []
            for prop, prop_type in props.items():
                if prop_type not in _PYTHON_TYPES:
                    raise InvalidDraftEndpointError(f"property {prop!r} of {name!r} has unsupported type {prop_type!r}")
                body.append(f"    {_field_name(prop)}: {_PYTHON_TYPES[prop_type]}")
            self.classes.append(f"class {nested}(BaseModel):\n" + ("\n".join(body) or "    pass"))
            return nested
        raise InvalidDraftEndpointError(f"structure of field {name!r} cannot be represented safely: {structure!r}")


def _constraints(name, entry: dict) -> str:
    constraints = entry.get("constraints") or {}
    parts = []
    for key, value in constraints.items():
        if key not in _CONSTRAINT_KEYS or entry.get("type") not in ("int", "float") or isinstance(value, bool) \
                or not isinstance(value, (int, float)):
            raise InvalidDraftEndpointError(f"constraint {key!r} on field {name!r} cannot be represented safely")
        parts.append(f"{_CONSTRAINT_KEYS[key]}={value!r}")
    return ", ".join(parts)


def _request_field(owner: str, models: _Models, name: str, entry: dict):
    """(annotation, default-source or None) for one documented parameter."""
    annotation = models.annotation(owner, name, entry)
    has_default = "default" in entry
    required = bool(entry.get("required")) and not has_default
    if has_default:
        default = repr(entry["default"])
    else:
        default = None if required else "None"
        if not required:
            annotation = f"Optional[{annotation}]"
    constraints = _constraints(name, entry)
    if constraints:
        return annotation, f"Field({default or '...'}, {constraints})"
    return annotation, default


class FastAPIApplicationGenerator(APIGenerator):
    """Turns one VALIDATED LLMAPIDocumentationDraft into a FastAPI module
    (returned as the package app/__init__.py + app/main.py, whose `app`
    object is the conventional entrypoint: `uvicorn app.main:app`) plus a requirements.txt
    listing only the packages that code imports plus the ASGI server, and a
    Dockerfile that installs that manifest and serves the app). It uses only what the draft contains:
    endpoint method/path, summary, description, parameters and responses.
    The draft carries no implementation, tags or operation ids, so none are
    invented. The handler never runs notebook code: it returns the draft's
    documented example output (header X-Execution: documented-example) when
    the request matches a documented example's input exactly, and otherwise
    answers 501. Output is deterministic (draft order, no timestamps)."""

    def generate(self, draft: LLMAPIDocumentationDraft) -> dict:
        method, _, path = draft.endpoint.partition(" ")
        if method not in _BODY_METHODS | _QUERY_METHODS or not path.startswith("/"):
            raise InvalidDraftEndpointError(f"unsupported endpoint {draft.endpoint!r}")

        prefix = _model_prefix(method, path)
        models = _Models()
        response_name = models.unique(prefix + "Response")
        request_name = models.unique(prefix + "Request") if method in _BODY_METHODS else None

        response_lines = [f"class {response_name}(BaseModel):"]
        for name, entry in draft.responses.items():
            name = _field_name(name)
            annotation = models.annotation(response_name, name, entry)
            response_lines.append(
                f"    {name}: Optional[{annotation}] = None" if entry.get("nullable") else f"    {name}: {annotation}"
            )
        if not draft.responses:
            response_lines.append("    pass")

        fields = []  # (name, annotation, default-source or None)
        for name, entry in draft.parameters.items():
            name = _field_name(name)
            annotation, default = _request_field(request_name or prefix, models, name, entry)
            fields.append((name, annotation, default))

        decorator = (
            f"@app.{method.lower()}({json.dumps(path)}, response_model={response_name}, "
            f"summary={json.dumps(draft.summary)}, description={json.dumps(draft.description)})"
        )
        blocks = []
        if method in _BODY_METHODS:
            body = [f"    {n}: {a}" + (f" = {d}" if d is not None else "") for n, a, d in fields]
            blocks.append(f"class {request_name}(BaseModel):\n" + ("\n".join(body) or "    pass"))
            signature = f"payload: {request_name}, response: Response"
            given = "payload.model_dump(exclude_unset=True)"
        else:
            args = [f"{n}: {a}" + (f" = {d}" if d is not None else "") for n, a, d in fields]
            args.sort(key=lambda arg: " = " in arg)  # defaults last; stable otherwise
            signature = ", ".join(["response: Response"] + args)
            given = "{k: v for k, v in {" + ", ".join(f"{json.dumps(n)}: {n}" for n, _, _ in fields) + "}.items() if v is not None}"

        lines = [
            "import json",
            "from typing import Optional",
            "",
            "from fastapi import FastAPI, HTTPException, Response",
            "from pydantic import BaseModel, Field",
            "",
            f"app = FastAPI(title={json.dumps(draft.summary)}, description={json.dumps(draft.description)})",
            f"EXAMPLES = json.loads({json.dumps(json.dumps(draft.examples))})",
            "",
        ]
        for block in models.classes + ["\n".join(response_lines)] + blocks:
            lines += ["", block, ""]
        lines += [
            "", decorator,
            f"def handler({signature}):",
            f"    given = {given}",
            "    for example in EXAMPLES:",
            '        if example["input"] == given:',
            '            response.headers["X-Execution"] = "documented-example"',
            '            return example["output"]',
            '    raise HTTPException(status_code=501, detail="Not implemented: no notebook logic is attached and no documented example matches this input")',
            "",
        ]
        files = {"app/__init__.py": "", "app/main.py": "\n".join(lines)}
        files["requirements.txt"] = generate_requirements(files, also=(ASGI_SERVER,))
        files["Dockerfile"] = generate_dockerfile(files)
        return files
