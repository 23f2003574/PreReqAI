import json
from datetime import datetime, timezone

from backend.api_candidates import LLMAPICandidateService
from backend.input_schema import LLMInputSchemaService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.output_schema import LLMOutputSchemaService

from .models import LLMAPIDocumentation


class MalformedDocumentationResponseError(ValueError):
    """Raised when the LLM's documentation response isn't well-formed."""


class ExampleSchemaMismatchError(ValueError):
    """Raised when an example's values don't conform to the inferred schema."""


class UnsupportedClaimError(ValueError):
    """Raised when an example references a parameter or response field the schema has no evidence for."""


class DuplicateDocumentationError(ValueError):
    """Raised when generate() is called twice for the same candidate_id -- use update()."""


class UnknownDocumentationError(KeyError):
    """Raised when update()/get()/validate() is called before generate() for a candidate_id."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are an API documentation assistant. Given a notebook function's "
    "source and its already-inferred parameters and response schema, write "
    "developer-facing documentation for it. Respond with ONLY a single JSON "
    "object -- no prose, no markdown fencing -- of the form {\"summary\": "
    "\"...\", \"description\": \"...\", \"examples\": [...]}. 'summary' is a "
    "short one-line string, 'description' is a longer string, and "
    "'examples' is a non-empty list of objects, each with 'input' (an "
    "object using only the given parameter names) and 'output' (an object "
    "using only the given response field names) -- every value must match "
    "the type already given for that field. Never invent a parameter or "
    "response field that isn't in the schema given to you."
)


def _matches_type(value, type_name: str) -> bool:
    if isinstance(value, bool):
        return type_name == "bool"
    if type_name == "int":
        return isinstance(value, int)
    if type_name == "float":
        return isinstance(value, (int, float))
    if type_name == "str":
        return isinstance(value, str)
    if type_name == "list":
        return isinstance(value, list)
    if type_name == "dict":
        return isinstance(value, dict)
    if type_name == "tuple":
        return isinstance(value, tuple)
    return False


class LLMAPIDocumentationService:
    """Generates versioned, schema-grounded API documentation for a candidate (Commit #3).

    parameters/response are always deterministically rebuilt from Commit #4's
    LLMInputSchema and Commit #5's LLMOutputSchema -- the LLM (via the same
    orchestration pipeline used throughout) only writes the summary,
    description, and examples, and every example is checked against those
    same schemas before being accepted. generate() creates the first
    version; update() creates every version after that -- each call appends
    an immutable snapshot rather than mutating the last one.
    """

    def __init__(
        self,
        api_candidate_service: LLMAPICandidateService,
        notebook_analysis_service: LLMNotebookAnalysisService,
        input_schema_service: LLMInputSchemaService,
        output_schema_service: LLMOutputSchemaService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._api_candidate_service = api_candidate_service
        self._notebook_analysis_service = notebook_analysis_service
        self._input_schema_service = input_schema_service
        self._output_schema_service = output_schema_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="api_documentation_generation", required_capabilities=["chat"]
        )
        self._history = {}
        self._request_counter = 0

    @staticmethod
    def _build_parameters(input_schema) -> dict:
        parameters = {}
        for field in input_schema.fields:
            entry = {"type": input_schema.types[field], "required": field in input_schema.required}
            if field in input_schema.defaults:
                entry["default"] = input_schema.defaults[field]
            if field in input_schema.constraints:
                entry["constraints"] = dict(input_schema.constraints[field])
            parameters[field] = entry
        return parameters

    @staticmethod
    def _build_response(output_schema) -> dict:
        response = {}
        for field in output_schema.fields:
            entry = {"type": output_schema.types[field], "nullable": field in output_schema.nullable}
            if field in output_schema.structure:
                entry["structure"] = dict(output_schema.structure[field])
            response[field] = entry
        return response

    def _collect_evidence(self, candidate_id: str):
        candidate = self._api_candidate_service.get(candidate_id)
        analysis = self._notebook_analysis_service.get_by_notebook(candidate.notebook_id)
        input_schema = self._input_schema_service.get(candidate_id)
        output_schema = self._output_schema_service.get(candidate_id)

        function = next(
            (fn for fn in analysis.functions if fn["name"] == candidate.function_name), None
        )
        if function is None or not isinstance(function.get("cell_index"), int):
            raise MalformedDocumentationResponseError(
                f"function {candidate.function_name!r} has no valid source in the analysis"
            )

        source = analysis.cells[function["cell_index"]].source
        return candidate, source, input_schema, output_schema

    @staticmethod
    def _build_prompt(candidate, source: str, parameters: dict, response: dict) -> str:
        payload = {
            "function_name": candidate.function_name,
            "source": source,
            "parameters": parameters,
            "response": response,
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str) -> dict:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedDocumentationResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict):
            raise MalformedDocumentationResponseError("LLM response must be a JSON object")

        for key in ("summary", "description"):
            if not isinstance(parsed.get(key), str) or not parsed[key].strip():
                raise MalformedDocumentationResponseError(f"'{key}' must be a non-empty string")

        examples = parsed.get("examples")
        if not isinstance(examples, list) or not examples:
            raise MalformedDocumentationResponseError("'examples' must be a non-empty list")

        for example in examples:
            if (
                not isinstance(example, dict)
                or not isinstance(example.get("input"), dict)
                or not isinstance(example.get("output"), dict)
            ):
                raise MalformedDocumentationResponseError(
                    "each example must be an object with 'input' and 'output' objects"
                )

        return parsed

    @staticmethod
    def _check_example(example: dict, input_schema, output_schema) -> None:
        input_payload = example["input"]
        output_payload = example["output"]

        unsupported = (set(input_payload) - set(input_schema.fields)) | (
            set(output_payload) - set(output_schema.fields)
        )
        if unsupported:
            raise UnsupportedClaimError(
                f"example references fields not present in the inferred schema: {sorted(unsupported)}"
            )

        missing_required = [field for field in input_schema.required if field not in input_payload]
        if missing_required:
            raise ExampleSchemaMismatchError(
                f"example input is missing required fields: {missing_required}"
            )

        for field, value in input_payload.items():
            if not _matches_type(value, input_schema.types[field]):
                raise ExampleSchemaMismatchError(
                    f"example input field {field!r} does not match inferred type "
                    f"{input_schema.types[field]!r}"
                )

        for field, value in output_payload.items():
            if value is None:
                if field not in output_schema.nullable:
                    raise ExampleSchemaMismatchError(
                        f"example output field {field!r} is None but the schema marks it non-nullable"
                    )
                continue
            if not _matches_type(value, output_schema.types[field]):
                raise ExampleSchemaMismatchError(
                    f"example output field {field!r} does not match inferred type "
                    f"{output_schema.types[field]!r}"
                )

    def _build_and_store(self, candidate_id: str) -> LLMAPIDocumentation:
        candidate, source, input_schema, output_schema = self._collect_evidence(candidate_id)
        parameters = self._build_parameters(input_schema)
        response = self._build_response(output_schema)

        self._request_counter += 1
        request_id = f"api-docs-{candidate_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(
                type="user",
                content=self._build_prompt(candidate, source, parameters, response),
                priority=1,
            ),
        )

        llm_response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if llm_response is None:
            raise MalformedDocumentationResponseError(f"LLM request failed: {decision.reason}")

        parsed = self._parse_response(llm_response.content)
        for example in parsed["examples"]:
            self._check_example(example, input_schema, output_schema)

        doc = LLMAPIDocumentation(
            candidate_id=candidate_id,
            summary=parsed["summary"],
            description=parsed["description"],
            parameters=parameters,
            response=response,
            examples=parsed["examples"],
            generated_at=datetime.now(timezone.utc),
        )
        self._history.setdefault(candidate_id, []).append(doc)
        return doc

    def generate(self, candidate_id: str) -> LLMAPIDocumentation:
        if candidate_id in self._history:
            raise DuplicateDocumentationError(
                f"documentation already generated for candidate_id {candidate_id!r}; use update()"
            )
        return self._build_and_store(candidate_id)

    def update(self, candidate_id: str) -> LLMAPIDocumentation:
        if candidate_id not in self._history:
            raise UnknownDocumentationError(candidate_id)
        return self._build_and_store(candidate_id)

    def get(self, candidate_id: str) -> LLMAPIDocumentation:
        try:
            return self._history[candidate_id][-1]
        except KeyError:
            raise UnknownDocumentationError(candidate_id)

    def history(self, candidate_id: str) -> list:
        """The full append-only version history, oldest first."""
        if candidate_id not in self._history:
            raise UnknownDocumentationError(candidate_id)
        return list(self._history[candidate_id])

    def validate(self, candidate_id: str) -> bool:
        """Re-checks the latest version's examples against the current schemas."""
        doc = self.get(candidate_id)
        input_schema = self._input_schema_service.get(candidate_id)
        output_schema = self._output_schema_service.get(candidate_id)

        for example in doc.examples:
            self._check_example(example, input_schema, output_schema)

        return True
