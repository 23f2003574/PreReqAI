import json
import keyword

from backend.api_documentation_draft import LLMAPIDocumentationDraft
from backend.input_schema import ALLOWED_TYPES

from .generator import APIGenerator

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


def _py_type(entry: dict) -> str:
    return _PYTHON_TYPES.get(entry.get("type"), "Any")


def _field_name(name: str) -> str:
    if not isinstance(name, str) or not name.isidentifier() or keyword.iskeyword(name):
        raise InvalidDraftEndpointError(f"field name {name!r} is not a valid Python identifier")
    return name


class FastAPIApplicationGenerator(APIGenerator):
    """Turns one VALIDATED LLMAPIDocumentationDraft into a FastAPI module
    (returned as {"main.py": source}). It uses only what the draft contains:
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

        lines = [
            "import json",
            "from typing import Any, Optional",
            "",
            "from fastapi import FastAPI, HTTPException, Response",
            "from pydantic import BaseModel",
            "",
            f"app = FastAPI(title={json.dumps(draft.summary)}, description={json.dumps(draft.description)})",
            f"EXAMPLES = json.loads({json.dumps(json.dumps(draft.examples))})",
            "",
        ]
        params = {_field_name(name): entry for name, entry in draft.parameters.items()}
        responses = {_field_name(name): entry for name, entry in draft.responses.items()}

        lines += ["", "class ResponseModel(BaseModel):"]
        for name, entry in responses.items():
            py = _py_type(entry)
            lines.append(f"    {name}: Optional[{py}] = None" if entry.get("nullable") else f"    {name}: {py}")
        if not responses:
            lines.append("    pass")

        decorator = (
            f"@app.{method.lower()}({json.dumps(path)}, response_model=ResponseModel, "
            f"summary={json.dumps(draft.summary)}, description={json.dumps(draft.description)})"
        )
        if method in _BODY_METHODS:
            lines += ["", "", "class RequestModel(BaseModel):"]
            for name, entry in params.items():
                py = _py_type(entry)
                lines.append(f"    {name}: {py}" if entry.get("required") else f"    {name}: Optional[{py}] = None")
            if not params:
                lines.append("    pass")
            signature = "payload: RequestModel, response: Response"
            given = "payload.model_dump(exclude_unset=True)"
        else:
            required = [f"{n}: {_py_type(e)}" for n, e in params.items() if e.get("required")]
            optional = [f"{n}: Optional[{_py_type(e)}] = None" for n, e in params.items() if not e.get("required")]
            signature = ", ".join(["response: Response"] + required + optional)
            given = "{" + ", ".join(f"{json.dumps(n)}: {n}" for n in params) + "}"
            given = "{k: v for k, v in " + given + ".items() if v is not None}"

        lines += [
            "", "",
            decorator,
            f"def handler({signature}):",
            f"    given = {given}",
            "    for example in EXAMPLES:",
            '        if example["input"] == given:',
            '            response.headers["X-Execution"] = "documented-example"',
            '            return example["output"]',
            '    raise HTTPException(status_code=501, detail="Not implemented: no notebook logic is attached and no documented example matches this input")',
            "",
        ]
        return {"main.py": "\n".join(lines)}
