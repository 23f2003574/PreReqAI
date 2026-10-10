import ast
import json

from backend.api_candidates import LLMAPICandidateService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService

from .models import ALLOWED_TYPES, LLMInputSchema

_NO_LITERAL = object()

_ANNOTATION_ALIASES = {
    "int": "int",
    "float": "float",
    "str": "str",
    "bool": "bool",
    "list": "list",
    "List": "list",
    "dict": "dict",
    "Dict": "dict",
    "tuple": "tuple",
    "Tuple": "tuple",
}


class MalformedSchemaResponseError(ValueError):
    """Raised when the LLM's schema response isn't well-formed, or source can't be read."""


class AmbiguousInputSchemaError(ValueError):
    """Raised when a field's type cannot be confidently determined."""


class InvalidSchemaError(ValueError):
    """Raised by validate() when a schema's fields/types/required/defaults/constraints
    are internally inconsistent."""


class UnknownSchemaError(KeyError):
    """Raised when looking up a candidate_id with no inferred schema."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are an API schema assistant. Given one notebook function's source and "
    "its parameter list, infer type information for parameters that have no "
    "explicit type annotation, plus any constraints implied by how each "
    "parameter is used. Respond with ONLY a single JSON object -- no prose, "
    "no markdown fencing -- of the form {\"fields\": [...]}. There must be "
    "exactly one entry per parameter, each an object with: 'name' (the "
    "parameter name), 'type' (one of int, float, str, bool, list, dict, "
    "tuple -- your best guess even if an explicit type was already given), "
    "'constraints' (an object of structured constraints, e.g. {\"min\": 0}, "
    "or {} if none), and 'ambiguous' (true only if you cannot confidently "
    "settle on a single type for that parameter)."
)


def _annotation_to_type(node):
    if node is None:
        return None
    try:
        text = ast.unparse(node)
    except Exception:
        return None
    base = text.split("[")[0].strip()
    return _ANNOTATION_ALIASES.get(base)


def _literal_default(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return _NO_LITERAL


def _find_function(source: str, function_name: str):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return node
    return None


def _signature_info(func_node) -> dict:
    """name -> {"required": bool, "explicit_type": str|None, "default": value|_NO_LITERAL}"""
    args = func_node.args
    positional = list(args.posonlyargs) + list(args.args)
    defaults = args.defaults
    num_no_default = len(positional) - len(defaults)

    info = {}
    for index, arg in enumerate(positional):
        has_default = index >= num_no_default
        default_value = _NO_LITERAL
        if has_default:
            default_value = _literal_default(defaults[index - num_no_default])
        info[arg.arg] = {
            "required": not has_default,
            "explicit_type": _annotation_to_type(arg.annotation),
            "default": default_value,
        }
    return info


class LLMInputSchemaService:
    """Infers a structured input schema for an API candidate (Commit #3).

    Explicit Python type annotations and literal defaults are read straight
    from the candidate's source function via `ast` -- deterministic, so they
    are always preserved as-is. The LLM (via the same orchestration pipeline
    used by every earlier commit) is only asked to fill in types for
    parameters that have no explicit annotation, and to suggest constraints;
    anything it can't confidently resolve is rejected rather than guessed.
    """

    def __init__(
        self,
        api_candidate_service: LLMAPICandidateService,
        notebook_analysis_service: LLMNotebookAnalysisService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._api_candidate_service = api_candidate_service
        self._notebook_analysis_service = notebook_analysis_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="input_schema_inference", required_capabilities=["chat"]
        )
        self._schemas = {}
        self._request_counter = 0

    @staticmethod
    def _build_prompt(function_name: str, source: str, fields: list) -> str:
        payload = {"function_name": function_name, "source": source, "fields": fields}
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, fields: list) -> dict:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedSchemaResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("fields"), list):
            raise MalformedSchemaResponseError("LLM response must be a JSON object with a 'fields' list")

        by_name = {}
        for entry in parsed["fields"]:
            if not isinstance(entry, dict):
                raise MalformedSchemaResponseError("each field entry must be an object")

            for key in ("name", "type", "constraints", "ambiguous"):
                if key not in entry:
                    raise MalformedSchemaResponseError(f"field entry missing required key {key!r}")

            name = entry["name"]
            if not isinstance(name, str) or name not in fields:
                raise MalformedSchemaResponseError(f"field entry names unknown parameter {name!r}")
            if not isinstance(entry["type"], str):
                raise MalformedSchemaResponseError(f"field {name!r} 'type' must be a string")
            if not isinstance(entry["constraints"], dict):
                raise MalformedSchemaResponseError(f"field {name!r} 'constraints' must be an object")
            if not isinstance(entry["ambiguous"], bool):
                raise MalformedSchemaResponseError(f"field {name!r} 'ambiguous' must be a boolean")

            by_name[name] = entry

        missing = [name for name in fields if name not in by_name]
        if missing:
            raise MalformedSchemaResponseError(f"LLM response is missing field entries for {missing}")

        return by_name

    def infer(self, candidate_id: str) -> LLMInputSchema:
        candidate = self._api_candidate_service.get(candidate_id)
        analysis = self._notebook_analysis_service.get_by_notebook(candidate.notebook_id)

        function = next(
            (fn for fn in analysis.functions if fn["name"] == candidate.function_name), None
        )
        if function is None:
            raise MalformedSchemaResponseError(
                f"function {candidate.function_name!r} not found in notebook {candidate.notebook_id!r}"
            )

        cell_index = function.get("cell_index")
        if not isinstance(cell_index, int) or not (0 <= cell_index < len(analysis.cells)):
            raise MalformedSchemaResponseError(f"function {candidate.function_name!r} has no valid cell_index")

        source = analysis.cells[cell_index].source
        func_node = _find_function(source, candidate.function_name)
        if func_node is None:
            raise MalformedSchemaResponseError(
                f"could not locate def {candidate.function_name}(...) in its source cell"
            )

        signature = _signature_info(func_node)
        fields = list(candidate.inputs)

        self._request_counter += 1
        request_id = f"input-schema-{candidate_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(
                type="user",
                content=self._build_prompt(candidate.function_name, source, fields),
                priority=1,
            ),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedSchemaResponseError(f"LLM request failed: {decision.reason}")

        inferred = self._parse_response(response.content, fields)

        types = {}
        required = []
        defaults = {}
        constraints = {}

        for field in fields:
            sig = signature.get(field, {"required": True, "explicit_type": None, "default": _NO_LITERAL})
            entry = inferred[field]

            if sig["explicit_type"] is not None:
                types[field] = sig["explicit_type"]
            else:
                if entry["ambiguous"]:
                    raise AmbiguousInputSchemaError(f"field {field!r} type is ambiguous")
                if entry["type"] not in ALLOWED_TYPES:
                    raise AmbiguousInputSchemaError(
                        f"field {field!r} inferred type {entry['type']!r} is not a recognized type"
                    )
                types[field] = entry["type"]

            if sig["required"]:
                required.append(field)
            elif sig["default"] is not _NO_LITERAL:
                defaults[field] = sig["default"]

            if entry["constraints"]:
                constraints[field] = dict(entry["constraints"])

        schema = LLMInputSchema(
            candidate_id=candidate_id,
            fields=fields,
            types=types,
            required=required,
            defaults=defaults,
            constraints=constraints,
        )
        self.validate(schema)

        self._schemas[candidate_id] = schema
        return schema

    @staticmethod
    def validate(schema: LLMInputSchema) -> bool:
        if not isinstance(schema.fields, list) or not schema.fields:
            raise InvalidSchemaError("schema.fields must be a non-empty list")
        if len(set(schema.fields)) != len(schema.fields):
            raise InvalidSchemaError("schema.fields must not contain duplicates")

        field_set = set(schema.fields)

        if set(schema.types) != field_set:
            raise InvalidSchemaError("schema.types must have exactly one entry per field")
        for field, field_type in schema.types.items():
            if field_type not in ALLOWED_TYPES:
                raise InvalidSchemaError(f"field {field!r} has unrecognized type {field_type!r}")

        if not set(schema.required) <= field_set:
            raise InvalidSchemaError("schema.required contains a field not in schema.fields")
        if len(set(schema.required)) != len(schema.required):
            raise InvalidSchemaError("schema.required must not contain duplicates")

        if not set(schema.defaults) <= field_set:
            raise InvalidSchemaError("schema.defaults contains a field not in schema.fields")
        if set(schema.defaults) & set(schema.required):
            raise InvalidSchemaError("a required field must not also have a default")

        if not set(schema.constraints) <= field_set:
            raise InvalidSchemaError("schema.constraints contains a field not in schema.fields")
        for field, field_constraints in schema.constraints.items():
            if not isinstance(field_constraints, dict):
                raise InvalidSchemaError(f"constraints for field {field!r} must be an object")

        return True

    def get(self, candidate_id: str) -> LLMInputSchema:
        """The full stored schema -- lets downstream commits reuse types/required/defaults/constraints."""
        try:
            return self._schemas[candidate_id]
        except KeyError:
            raise UnknownSchemaError(candidate_id)

    def fields(self, candidate_id: str) -> list:
        return list(self.get(candidate_id).fields)
