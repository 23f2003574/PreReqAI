import json
from datetime import datetime, timezone

from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService

from .models import LLMNotebookSummary


class MalformedSummaryResponseError(ValueError):
    """Raised when the LLM's summary response isn't well-formed, or references
    a function/dependency the notebook's own analysis doesn't actually have."""


class UnknownSummaryError(KeyError):
    """Raised when get_summary() is called for a notebook_id with no summary yet."""


SUMMARY_SYSTEM_PROMPT = (
    "You are a notebook summarization assistant. Given a notebook's "
    "structured analysis -- its known functions and imports -- produce a "
    "semantic summary. Respond with ONLY a single JSON object -- no prose, "
    "no markdown fencing -- of the form {\"purpose\": \"...\", "
    "\"key_components\": [...], \"inputs\": [...], \"outputs\": [...], "
    "\"dependencies\": [...]}. 'purpose' is a short description of what "
    "the notebook does. 'key_components' is a list of objects, each with "
    "'name' (must exactly match one of the given function names) and "
    "'description' (its role in the notebook) -- an empty list if the "
    "notebook defines no functions. 'inputs' and 'outputs' are lists of "
    "short strings describing what the notebook consumes and produces. "
    "'dependencies' is a list of strings, each taken only from the given "
    "imports -- never invent a dependency that isn't listed, and never "
    "invent a function name that isn't given."
)


class LLMNotebookSummaryService:
    """Produces a structured, LLM-backed semantic summary of an existing notebook.

    Reuses backend.notebook_analysis.LLMNotebookAnalysisService for the
    ground-truth functions/imports a summary must reference, and the same
    LLM orchestration pipeline used throughout this codebase -- this
    service never re-parses notebook source itself (it only ever reads an
    already-produced analysis) and never touches the compiler. Every
    key_components entry and every dependency the LLM proposes is checked
    against that analysis; anything that isn't well-formed or references a
    function/dependency the notebook doesn't actually have is rejected.
    """

    def __init__(
        self,
        notebook_analysis_service: LLMNotebookAnalysisService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._notebook_analysis_service = notebook_analysis_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="notebook_summary", required_capabilities=["chat"]
        )
        self._summaries_by_notebook = {}
        self._request_counter = 0

    @staticmethod
    def _build_prompt(analysis) -> str:
        payload = {
            "notebook_id": analysis.notebook_id,
            "functions": [fn["name"] for fn in analysis.functions],
            "imports": list(analysis.imports),
            "dependencies": list(analysis.dependencies),
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, known_functions: set, known_dependencies: set) -> dict:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedSummaryResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict):
            raise MalformedSummaryResponseError("LLM response must be a JSON object")

        for key in ("purpose", "key_components", "inputs", "outputs", "dependencies"):
            if key not in parsed:
                raise MalformedSummaryResponseError(f"LLM response missing required field {key!r}")

        if not isinstance(parsed["purpose"], str) or not parsed["purpose"].strip():
            raise MalformedSummaryResponseError("'purpose' must be a non-empty string")

        if not isinstance(parsed["key_components"], list):
            raise MalformedSummaryResponseError("'key_components' must be a list")
        for component in parsed["key_components"]:
            if (
                not isinstance(component, dict)
                or "name" not in component
                or "description" not in component
            ):
                raise MalformedSummaryResponseError(
                    "each key_components entry must be an object with 'name' and 'description'"
                )
            if component["name"] not in known_functions:
                raise MalformedSummaryResponseError(
                    f"key_components references unknown function {component['name']!r}"
                )
            if not isinstance(component["description"], str) or not component["description"].strip():
                raise MalformedSummaryResponseError("key_components 'description' must be a non-empty string")

        for key in ("inputs", "outputs"):
            if not isinstance(parsed[key], list) or not all(
                isinstance(item, str) and item.strip() for item in parsed[key]
            ):
                raise MalformedSummaryResponseError(f"{key!r} must be a list of non-empty strings")

        if not isinstance(parsed["dependencies"], list):
            raise MalformedSummaryResponseError("'dependencies' must be a list")
        for dependency in parsed["dependencies"]:
            if not isinstance(dependency, str) or dependency not in known_dependencies:
                raise MalformedSummaryResponseError(
                    f"dependency {dependency!r} was not among the notebook's known imports/dependencies"
                )

        return parsed

    def summarize(self, notebook_id: str) -> LLMNotebookSummary:
        analysis = self._notebook_analysis_service.get_by_notebook(notebook_id)

        known_functions = {fn["name"] for fn in analysis.functions}
        known_dependencies = set(analysis.imports) | set(analysis.dependencies)

        self._request_counter += 1
        request_id = f"notebook-summary-{notebook_id}-{self._request_counter}"

        self._context_service.create(request_id, system=SUMMARY_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(analysis), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedSummaryResponseError(f"LLM request failed: {decision.reason}")

        parsed = self._parse_response(response.content, known_functions, known_dependencies)

        summary = LLMNotebookSummary(
            notebook_id=notebook_id,
            purpose=parsed["purpose"],
            key_components=[dict(component) for component in parsed["key_components"]],
            inputs=list(parsed["inputs"]),
            outputs=list(parsed["outputs"]),
            dependencies=list(parsed["dependencies"]),
            generated_at=datetime.now(timezone.utc),
        )
        self._summaries_by_notebook[notebook_id] = summary
        return summary

    def get_summary(self, notebook_id: str) -> LLMNotebookSummary:
        try:
            return self._summaries_by_notebook[notebook_id]
        except KeyError:
            raise UnknownSummaryError(notebook_id)
