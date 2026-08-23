import json

from backend.api_candidates import LLMAPICandidateService
from backend.input_schema import LLMInputSchemaService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.output_schema import LLMOutputSchemaService

from .models import CATEGORIES, INVALID, LLMGeneratedTest


class MalformedTestError(ValueError):
    """Raised when the LLM's generated-test response isn't well-formed."""


class UnknownTestFieldError(ValueError):
    """Raised when a generated test references a field not in the inferred schema."""


class UnknownTestError(KeyError):
    """Raised when looking up a test_id that was never generated."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are a test design assistant. Given an API candidate's inferred "
    "input and output schema, write test cases for it. Respond with ONLY a "
    "single JSON object -- no prose, no markdown fencing -- of the form "
    "{\"tests\": [...]}. Each test is an object with: 'scenario' (a short "
    "description), 'category' (one of VALID, INVALID, EDGE), 'input' (an "
    "object using only the given parameter names), 'expected_output', and "
    "'confidence' (a number between 0.0 and 1.0). For VALID/EDGE tests, "
    "'input' must satisfy every required field and type, and "
    "'expected_output' is an object using only the given response field "
    "names with values matching their types. For INVALID tests, 'input' "
    "must genuinely violate the schema (a missing required field or a wrong "
    "type), and 'expected_output' must be exactly "
    "{\"raises\": true, \"reason\": \"<short string>\"} since an invalid "
    "payload is rejected before it ever runs. Include at least one test in "
    "each of the three categories. Never invent a field that isn't in the "
    "given schema."
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


class LLMTestGenerationService:
    """Generates structured test cases for an API candidate (Commit #3).

    Reuses the candidate itself, Commit #4's LLMInputSchema, Commit #5's
    LLMOutputSchema, and the same LLM orchestration pipeline used throughout.
    Every generated test is checked against those schemas before it's
    stored: no test may reference a field the schema doesn't have, a
    VALID/EDGE test's input/expected_output must be fully schema-conformant,
    and an INVALID test's input must genuinely violate the schema. Generated
    tests are inert records -- this service never executes the candidate
    function, here or anywhere else in this commit.
    """

    def __init__(
        self,
        api_candidate_service: LLMAPICandidateService,
        input_schema_service: LLMInputSchemaService,
        output_schema_service: LLMOutputSchemaService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._api_candidate_service = api_candidate_service
        self._input_schema_service = input_schema_service
        self._output_schema_service = output_schema_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="test_generation", required_capabilities=["chat"]
        )
        self._tests_by_candidate = {}
        self._tests_by_id = {}
        self._request_counter = 0
        self._test_counter = 0

    @staticmethod
    def _build_prompt(candidate, input_schema, output_schema) -> str:
        payload = {
            "function_name": candidate.function_name,
            "rationale": candidate.rationale,
            "input_schema": {
                "types": input_schema.types,
                "required": input_schema.required,
                "defaults": input_schema.defaults,
                "constraints": input_schema.constraints,
            },
            "output_schema": {
                "types": output_schema.types,
                "nullable": output_schema.nullable,
                "structure": output_schema.structure,
            },
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedTestError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("tests"), list) or not parsed["tests"]:
            raise MalformedTestError("LLM response must be a JSON object with a non-empty 'tests' list")

        tests = parsed["tests"]
        for test in tests:
            if not isinstance(test, dict):
                raise MalformedTestError("each test must be an object")

            for key in ("scenario", "category", "input", "expected_output", "confidence"):
                if key not in test:
                    raise MalformedTestError(f"test missing required field {key!r}")

            if not isinstance(test["scenario"], str) or not test["scenario"].strip():
                raise MalformedTestError("test 'scenario' must be a non-empty string")
            if test["category"] not in CATEGORIES:
                raise MalformedTestError(
                    f"test category {test['category']!r} must be one of {sorted(CATEGORIES)}"
                )
            if not isinstance(test["input"], dict) or not isinstance(test["expected_output"], dict):
                raise MalformedTestError("test 'input' and 'expected_output' must be objects")

            confidence = test["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedTestError("test 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedTestError("test 'confidence' must be between 0.0 and 1.0")

        seen_categories = {test["category"] for test in tests}
        missing = CATEGORIES - seen_categories
        if missing:
            raise MalformedTestError(f"response is missing test categories: {sorted(missing)}")

        return tests

    @staticmethod
    def _check_test(test: dict, input_schema, output_schema) -> None:
        input_payload = test["input"]
        expected = test["expected_output"]
        category = test["category"]

        unsupported_input = set(input_payload) - set(input_schema.fields)
        if unsupported_input:
            raise UnknownTestFieldError(
                f"test input references fields not in the inferred schema: {sorted(unsupported_input)}"
            )

        if category == INVALID:
            if expected.get("raises") is not True or not isinstance(expected.get("reason"), str) or not expected[
                "reason"
            ].strip():
                raise MalformedTestError(
                    "INVALID test expected_output must be {'raises': true, 'reason': '<non-empty string>'}"
                )

            missing_required = [f for f in input_schema.required if f not in input_payload]
            type_violation = any(
                field in input_schema.types and not _matches_type(value, input_schema.types[field])
                for field, value in input_payload.items()
            )
            if not missing_required and not type_violation:
                raise MalformedTestError(
                    "INVALID test input does not actually violate the inferred schema"
                )
            return

        missing_required = [f for f in input_schema.required if f not in input_payload]
        if missing_required:
            raise MalformedTestError(f"{category} test input is missing required fields: {missing_required}")

        for field, value in input_payload.items():
            if not _matches_type(value, input_schema.types[field]):
                raise MalformedTestError(
                    f"{category} test input field {field!r} does not match inferred type "
                    f"{input_schema.types[field]!r}"
                )

        unsupported_output = set(expected) - set(output_schema.fields)
        if unsupported_output:
            raise UnknownTestFieldError(
                f"test expected_output references fields not in the inferred schema: "
                f"{sorted(unsupported_output)}"
            )

        for field, value in expected.items():
            if value is None:
                if field not in output_schema.nullable:
                    raise MalformedTestError(
                        f"expected_output field {field!r} is None but the schema marks it non-nullable"
                    )
                continue
            if not _matches_type(value, output_schema.types[field]):
                raise MalformedTestError(
                    f"expected_output field {field!r} does not match inferred type "
                    f"{output_schema.types[field]!r}"
                )

    def generate(self, candidate_id: str) -> list:
        candidate = self._api_candidate_service.get(candidate_id)
        input_schema = self._input_schema_service.get(candidate_id)
        output_schema = self._output_schema_service.get(candidate_id)

        self._request_counter += 1
        request_id = f"test-generation-{candidate_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(
                type="user",
                content=self._build_prompt(candidate, input_schema, output_schema),
                priority=1,
            ),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedTestError(f"LLM request failed: {decision.reason}")

        raw_tests = self._parse_response(response.content)
        for test in raw_tests:
            self._check_test(test, input_schema, output_schema)

        created = []
        for test in raw_tests:
            self._test_counter += 1
            record = LLMGeneratedTest(
                test_id=f"test-{candidate_id}-{self._test_counter}",
                candidate_id=candidate_id,
                scenario=test["scenario"],
                input=dict(test["input"]),
                expected_output=dict(test["expected_output"]),
                category=test["category"],
                confidence=float(test["confidence"]),
            )
            created.append(record)
            self._tests_by_id[record.test_id] = record

        self._tests_by_candidate.setdefault(candidate_id, []).extend(created)
        return created

    def tests(self, candidate_id: str) -> list:
        return list(self._tests_by_candidate.get(candidate_id, []))

    def validate(self, test_id: str) -> bool:
        try:
            test = self._tests_by_id[test_id]
        except KeyError:
            raise UnknownTestError(test_id)

        input_schema = self._input_schema_service.get(test.candidate_id)
        output_schema = self._output_schema_service.get(test.candidate_id)

        self._check_test(
            {
                "category": test.category,
                "input": test.input,
                "expected_output": test.expected_output,
            },
            input_schema,
            output_schema,
        )
        return True
