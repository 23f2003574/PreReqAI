import ast
import json

from backend.api_candidates import LLMAPICandidateService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService

from .models import ALLOWED_TYPES, STRUCTURED_TYPES, LLMOutputSchema

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


class MalformedOutputSchemaResponseError(ValueError):
    """Raised when the LLM's schema response isn't well-formed, or source can't be read."""


class ContradictoryOutputSchemaError(ValueError):
    """Raised when the type evidence for a field is contradictory or unresolvable."""


class InvalidOutputSchemaError(ValueError):
    """Raised by validate() when a schema's fields/types/nullable/structure are
    internally inconsistent."""


class UnknownOutputSchemaError(KeyError):
    """Raised when looking up a candidate_id with no inferred output schema."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are an API schema assistant. Given one notebook function's source and "
    "its declared output fields, infer type information for each output field "
    "from its return values and how it is used downstream. Respond with ONLY a "
    "single JSON object -- no prose, no markdown fencing -- of the form "
    "{\"fields\": [...]}. There must be exactly one entry per output field, "
    "each an object with: 'name' (the output field name), 'type' (one of int, "
    "float, str, bool, list, dict, tuple -- your best guess even if other "
    "evidence already fixes it), 'nullable' (true if the field can be None), "
    "'structure' (for list/dict types, a nested descriptor of the shape, or "
    "{} otherwise), and 'contradictory' (true only if usage elsewhere in the "
    "notebook is inconsistent with a single settled type for that field)."
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


def _find_function(source: str, function_name: str):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return node
    return None


class _ReturnCollector(ast.NodeVisitor):
    """Collects `return` statements belonging to one function, not its nested ones."""

    def __init__(self):
        self.returns = []

    def visit_FunctionDef(self, node):
        pass

    def visit_AsyncFunctionDef(self, node):
        pass

    def visit_Lambda(self, node):
        pass

    def visit_Return(self, node):
        self.returns.append(node)


def _collect_returns(func_node):
    collector = _ReturnCollector()
    collector.generic_visit(func_node)
    return collector.returns


def _python_type_name(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, tuple):
        return "tuple"
    if isinstance(value, dict):
        return "dict"
    return None


def _structure_or_type(value):
    if isinstance(value, dict):
        return {"type": "object", "properties": {k: _structure_or_type(v) for k, v in value.items()}}
    if isinstance(value, (list, tuple)):
        if not value:
            return {"type": "list", "items": None}
        return {"type": "list", "items": _structure_or_type(value[0])}
    return _python_type_name(value)


def _structure_of(value) -> dict:
    if isinstance(value, dict):
        return {"type": "object", "properties": {k: _structure_or_type(v) for k, v in value.items()}}
    if isinstance(value, (list, tuple)):
        if not value:
            return {"type": "list", "items": None}
        return {"type": "list", "items": _structure_or_type(value[0])}
    return {}


def _literal_values_by_field(func_node, outputs: list) -> dict:
    values = {field: [] for field in outputs}

    for ret in _collect_returns(func_node):
        if ret.value is None:
            if len(outputs) == 1:
                values[outputs[0]].append(None)
            continue

        if isinstance(ret.value, ast.Tuple) and len(outputs) > 1 and len(ret.value.elts) == len(outputs):
            for field, elt in zip(outputs, ret.value.elts):
                try:
                    values[field].append(ast.literal_eval(elt))
                except (ValueError, TypeError, SyntaxError):
                    pass
            continue

        if len(outputs) == 1:
            try:
                values[outputs[0]].append(ast.literal_eval(ret.value))
            except (ValueError, TypeError, SyntaxError):
                pass

    return values


class LLMOutputSchemaService:
    """Infers a structured output (response) schema for an API candidate (Commit #3).

    Type evidence is gathered deterministically first -- the function's return
    type annotation and any literal return values, read via `ast` -- and only
    a field left unresolved by that evidence is handed to the LLM (via the
    same orchestration pipeline used by every earlier commit). Evidence that
    disagrees with itself, whether found statically or flagged by the LLM, is
    rejected rather than guessed at.
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
            task="output_schema_inference", required_capabilities=["chat"]
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
            raise MalformedOutputSchemaResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("fields"), list):
            raise MalformedOutputSchemaResponseError(
                "LLM response must be a JSON object with a 'fields' list"
            )

        by_name = {}
        for entry in parsed["fields"]:
            if not isinstance(entry, dict):
                raise MalformedOutputSchemaResponseError("each field entry must be an object")

            for key in ("name", "type", "nullable", "structure", "contradictory"):
                if key not in entry:
                    raise MalformedOutputSchemaResponseError(f"field entry missing required key {key!r}")

            name = entry["name"]
            if not isinstance(name, str) or name not in fields:
                raise MalformedOutputSchemaResponseError(f"field entry names unknown output {name!r}")
            if not isinstance(entry["type"], str):
                raise MalformedOutputSchemaResponseError(f"field {name!r} 'type' must be a string")
            if not isinstance(entry["nullable"], bool):
                raise MalformedOutputSchemaResponseError(f"field {name!r} 'nullable' must be a boolean")
            if not isinstance(entry["structure"], dict):
                raise MalformedOutputSchemaResponseError(f"field {name!r} 'structure' must be an object")
            if not isinstance(entry["contradictory"], bool):
                raise MalformedOutputSchemaResponseError(f"field {name!r} 'contradictory' must be a boolean")

            by_name[name] = entry

        missing = [name for name in fields if name not in by_name]
        if missing:
            raise MalformedOutputSchemaResponseError(f"LLM response is missing field entries for {missing}")

        return by_name

    def infer(self, candidate_id: str) -> LLMOutputSchema:
        candidate = self._api_candidate_service.get(candidate_id)
        analysis = self._notebook_analysis_service.get_by_notebook(candidate.notebook_id)

        function = next(
            (fn for fn in analysis.functions if fn["name"] == candidate.function_name), None
        )
        if function is None:
            raise MalformedOutputSchemaResponseError(
                f"function {candidate.function_name!r} not found in notebook {candidate.notebook_id!r}"
            )

        cell_index = function.get("cell_index")
        if not isinstance(cell_index, int) or not (0 <= cell_index < len(analysis.cells)):
            raise MalformedOutputSchemaResponseError(
                f"function {candidate.function_name!r} has no valid cell_index"
            )

        source = analysis.cells[cell_index].source
        func_node = _find_function(source, candidate.function_name)
        if func_node is None:
            raise MalformedOutputSchemaResponseError(
                f"could not locate def {candidate.function_name}(...) in its source cell"
            )

        fields = list(candidate.outputs)
        if not fields:
            raise MalformedOutputSchemaResponseError(
                f"candidate {candidate_id!r} has no declared output fields"
            )

        explicit_type = _annotation_to_type(func_node.returns) if len(fields) == 1 else None
        literal_values = _literal_values_by_field(func_node, fields)

        deterministic = {}
        for field in fields:
            values = literal_values[field]
            saw_none = any(value is None for value in values)
            non_none = [value for value in values if value is not None]
            distinct_types = {_python_type_name(value) for value in non_none}

            if len(distinct_types) > 1:
                raise ContradictoryOutputSchemaError(
                    f"field {field!r} has contradictory literal return types: {sorted(distinct_types)}"
                )

            literal_type = next(iter(distinct_types)) if distinct_types else None
            field_explicit = explicit_type

            if field_explicit and literal_type and field_explicit != literal_type:
                raise ContradictoryOutputSchemaError(
                    f"field {field!r} return annotation {field_explicit!r} conflicts with "
                    f"observed literal return type {literal_type!r}"
                )

            resolved_type = field_explicit or literal_type
            structure = {}
            representative = next(
                (value for value in reversed(non_none) if isinstance(value, (list, tuple, dict))), None
            )
            if representative is not None:
                structure = _structure_of(representative)

            deterministic[field] = {
                "type": resolved_type,
                "nullable": saw_none if (resolved_type or saw_none) else None,
                "structure": structure,
            }

        self._request_counter += 1
        request_id = f"output-schema-{candidate_id}-{self._request_counter}"

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
            raise MalformedOutputSchemaResponseError(f"LLM request failed: {decision.reason}")

        inferred = self._parse_response(response.content, fields)

        types = {}
        nullable = []
        structure = {}

        for field in fields:
            entry = inferred[field]
            det = deterministic[field]

            if entry["contradictory"]:
                raise ContradictoryOutputSchemaError(f"field {field!r} usage is contradictory")

            if det["type"] is not None:
                field_type = det["type"]
            else:
                if entry["type"] not in ALLOWED_TYPES:
                    raise ContradictoryOutputSchemaError(
                        f"field {field!r} inferred type {entry['type']!r} is not a recognized type"
                    )
                field_type = entry["type"]
            types[field] = field_type

            field_nullable = det["nullable"] if det["nullable"] is not None else entry["nullable"]
            if field_nullable:
                nullable.append(field)

            if field_type in STRUCTURED_TYPES:
                structure[field] = det["structure"] if det["structure"] else entry["structure"]

        schema = LLMOutputSchema(
            candidate_id=candidate_id, fields=fields, types=types, nullable=nullable, structure=structure
        )
        self.validate(schema)

        self._schemas[candidate_id] = schema
        return schema

    @staticmethod
    def validate(schema: LLMOutputSchema) -> bool:
        if not isinstance(schema.fields, list) or not schema.fields:
            raise InvalidOutputSchemaError("schema.fields must be a non-empty list")
        if len(set(schema.fields)) != len(schema.fields):
            raise InvalidOutputSchemaError("schema.fields must not contain duplicates")

        field_set = set(schema.fields)

        if set(schema.types) != field_set:
            raise InvalidOutputSchemaError("schema.types must have exactly one entry per field")
        for field, field_type in schema.types.items():
            if field_type not in ALLOWED_TYPES:
                raise InvalidOutputSchemaError(f"field {field!r} has unrecognized type {field_type!r}")

        if not set(schema.nullable) <= field_set:
            raise InvalidOutputSchemaError("schema.nullable contains a field not in schema.fields")
        if len(set(schema.nullable)) != len(schema.nullable):
            raise InvalidOutputSchemaError("schema.nullable must not contain duplicates")

        if not set(schema.structure) <= field_set:
            raise InvalidOutputSchemaError("schema.structure contains a field not in schema.fields")
        for field, field_structure in schema.structure.items():
            if not isinstance(field_structure, dict):
                raise InvalidOutputSchemaError(f"structure for field {field!r} must be an object")
            if schema.types[field] not in STRUCTURED_TYPES and field_structure:
                raise InvalidOutputSchemaError(
                    f"field {field!r} has type {schema.types[field]!r} but a non-empty structure"
                )

        return True

    def fields(self, candidate_id: str) -> list:
        try:
            return list(self._schemas[candidate_id].fields)
        except KeyError:
            raise UnknownOutputSchemaError(candidate_id)
