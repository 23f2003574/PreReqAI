import json

from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_summary import LLMNotebookSummaryService, UnknownSummaryError

from .models import EXPOSURE_LEVELS, LLMNotebookAPIIntent


class MalformedIntentResponseError(ValueError):
    """Raised when the LLM's intent response isn't well-formed."""


class UnknownIntentFunctionError(ValueError):
    """Raised when an operation or candidate function references a function
    the notebook's own analysis doesn't actually have."""


class UnknownIntentError(KeyError):
    """Raised when get() is called for a notebook_id with no extracted intent yet."""


INTENT_SYSTEM_PROMPT = (
    "You are an API intent extraction assistant. Given a notebook's "
    "structured analysis (its known functions) and, if available, a "
    "semantic summary of its purpose, extract the user's intended API "
    "behavior. Respond with ONLY a single JSON object -- no prose, no "
    "markdown fencing -- of the form {\"operations\": [...], "
    "\"candidate_functions\": [...], \"requested_exposure\": \"...\", "
    "\"constraints\": [...], \"confidence\": 0.0}. 'operations' is a "
    "non-empty list of objects, each with 'operation' (a short "
    "description of the intended API action), 'function' (must exactly "
    "match one of the given function names, or null if you cannot "
    "confidently map this operation to one function), and 'ambiguous' "
    "(true if you are not confident enough to name a single function -- "
    "when true, 'function' must be null; never guess a function you "
    "aren't confident about). 'candidate_functions' is a list of function "
    "names, each taken only from the given functions. "
    "'requested_exposure' is one of PUBLIC, INTERNAL, READ_ONLY, or "
    "UNSPECIFIED. 'constraints' is a list of short strings describing any "
    "constraints implied by the notebook (an empty list if none). "
    "'confidence' is a number between 0.0 and 1.0 for the extraction as a "
    "whole."
)


class LLMNotebookAPIIntentService:
    """Extracts the user's intended API behavior from an already-parsed notebook.

    Reuses backend.notebook_analysis.LLMNotebookAnalysisService for the
    ground-truth functions an intent must reference, and (where available)
    Commit #2's LLMNotebookSummaryService for the notebook's purpose --
    extract() proceeds without a summary if one was never generated, since
    intent extraction only strictly depends on the analysis. Every
    operation's function mapping and every candidate function the LLM
    proposes is checked against that analysis; an operation the LLM isn't
    confident about must be flagged ambiguous with no function guessed,
    never silently resolved. This service never re-parses notebook source
    itself and never touches the compiler.
    """

    def __init__(
        self,
        notebook_analysis_service: LLMNotebookAnalysisService,
        summary_service: LLMNotebookSummaryService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._notebook_analysis_service = notebook_analysis_service
        self._summary_service = summary_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="notebook_api_intent", required_capabilities=["chat"]
        )
        self._intents_by_notebook = {}
        self._request_counter = 0

    @staticmethod
    def _build_prompt(analysis, summary) -> str:
        payload = {
            "notebook_id": analysis.notebook_id,
            "functions": [fn["name"] for fn in analysis.functions],
            "imports": list(analysis.imports),
        }
        if summary is not None:
            payload["summary"] = {
                "purpose": summary.purpose,
                "inputs": summary.inputs,
                "outputs": summary.outputs,
            }
        return json.dumps(payload)

    @staticmethod
    def _check_operations(operations, known_functions: set) -> None:
        if not isinstance(operations, list) or not operations:
            raise MalformedIntentResponseError("'operations' must be a non-empty list")

        for operation in operations:
            if not isinstance(operation, dict):
                raise MalformedIntentResponseError("each operation must be an object")
            for key in ("operation", "function", "ambiguous"):
                if key not in operation:
                    raise MalformedIntentResponseError(f"operation missing required field {key!r}")
            if not isinstance(operation["operation"], str) or not operation["operation"].strip():
                raise MalformedIntentResponseError("operation 'operation' must be a non-empty string")
            if not isinstance(operation["ambiguous"], bool):
                raise MalformedIntentResponseError("operation 'ambiguous' must be a boolean")

            if operation["ambiguous"]:
                if operation["function"] is not None:
                    raise MalformedIntentResponseError(
                        "an ambiguous operation must not guess a function -- 'function' must be null"
                    )
            elif operation["function"] not in known_functions:
                raise UnknownIntentFunctionError(
                    f"operation references unknown function {operation['function']!r}"
                )

    @classmethod
    def _parse_response(cls, raw_content: str, known_functions: set) -> dict:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedIntentResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict):
            raise MalformedIntentResponseError("LLM response must be a JSON object")

        for key in ("operations", "candidate_functions", "requested_exposure", "constraints", "confidence"):
            if key not in parsed:
                raise MalformedIntentResponseError(f"LLM response missing required field {key!r}")

        cls._check_operations(parsed["operations"], known_functions)

        candidate_functions = parsed["candidate_functions"]
        if not isinstance(candidate_functions, list):
            raise MalformedIntentResponseError("'candidate_functions' must be a list")
        unknown = [fn for fn in candidate_functions if fn not in known_functions]
        if unknown:
            raise UnknownIntentFunctionError(f"candidate_functions references unknown functions: {unknown}")

        if parsed["requested_exposure"] not in EXPOSURE_LEVELS:
            raise MalformedIntentResponseError(
                f"'requested_exposure' must be one of {sorted(EXPOSURE_LEVELS)}"
            )

        constraints = parsed["constraints"]
        if not isinstance(constraints, list) or not all(
            isinstance(constraint, str) and constraint.strip() for constraint in constraints
        ):
            raise MalformedIntentResponseError("'constraints' must be a list of non-empty strings")

        confidence = parsed["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise MalformedIntentResponseError("'confidence' must be a number")
        if not (0.0 <= float(confidence) <= 1.0):
            raise MalformedIntentResponseError("'confidence' must be between 0.0 and 1.0")

        return parsed

    def extract(self, notebook_id: str) -> LLMNotebookAPIIntent:
        analysis = self._notebook_analysis_service.get_by_notebook(notebook_id)
        known_functions = {fn["name"] for fn in analysis.functions}

        try:
            summary = self._summary_service.get_summary(notebook_id)
        except UnknownSummaryError:
            summary = None

        self._request_counter += 1
        request_id = f"notebook-api-intent-{notebook_id}-{self._request_counter}"

        self._context_service.create(request_id, system=INTENT_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(analysis, summary), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedIntentResponseError(f"LLM request failed: {decision.reason}")

        parsed = self._parse_response(response.content, known_functions)

        intent = LLMNotebookAPIIntent(
            notebook_id=notebook_id,
            operations=[dict(operation) for operation in parsed["operations"]],
            candidate_functions=list(parsed["candidate_functions"]),
            requested_exposure=parsed["requested_exposure"],
            constraints=list(parsed["constraints"]),
            confidence=float(parsed["confidence"]),
        )
        self._intents_by_notebook[notebook_id] = intent
        return intent

    def validate(self, intent: LLMNotebookAPIIntent) -> bool:
        analysis = self._notebook_analysis_service.get_by_notebook(intent.notebook_id)
        known_functions = {fn["name"] for fn in analysis.functions}

        for operation in intent.operations:
            if not operation["ambiguous"] and operation["function"] not in known_functions:
                raise UnknownIntentFunctionError(
                    f"intent for {intent.notebook_id!r} references a function that no longer "
                    f"exists: {operation['function']!r}"
                )

        unknown_candidates = [fn for fn in intent.candidate_functions if fn not in known_functions]
        if unknown_candidates:
            raise UnknownIntentFunctionError(
                f"intent for {intent.notebook_id!r} references functions that no longer exist: "
                f"{unknown_candidates}"
            )

        return True

    def get(self, notebook_id: str) -> LLMNotebookAPIIntent:
        try:
            return self._intents_by_notebook[notebook_id]
        except KeyError:
            raise UnknownIntentError(notebook_id)
