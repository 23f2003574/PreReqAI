import json

from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_dependencies import LLMNotebookDependencyService

from .models import LLMAPICandidate


class MalformedCandidateResponseError(ValueError):
    """Raised when the LLM's candidate response is not a well-formed candidate list."""


class UnknownFunctionCandidateError(ValueError):
    """Raised when a candidate references a function not present in the analysis."""


class UnknownCandidateError(KeyError):
    """Raised when looking up a candidate_id that was never produced."""


ANALYSIS_SYSTEM_PROMPT = (
    "You are an API design assistant. Given a notebook's structured analysis "
    "(its functions and their source) and, where available, its dependency "
    "graph, identify which functions are good candidates for exposure as an "
    "API. Respond with ONLY a single JSON object -- no prose, no markdown "
    "fencing -- of the form {\"candidates\": [...]}. Each candidate is an "
    "object with: 'function_name' (must exactly match one of the given "
    "function names), 'inputs' (a list of input names inferred from the "
    "function and its usage), 'outputs' (a list of output names inferred the "
    "same way), 'confidence' (a number between 0.0 and 1.0), and 'rationale' "
    "(a short string explaining why the function is a good API candidate). "
    "Never rename, rewrite, or otherwise alter the source function."
)


class LLMAPICandidateService:
    """Identifies notebook functions worth exposing as an API.

    Reuses Commit #1's LLMNotebookAnalysisService for the ground-truth set of
    functions a candidate must reference, Commit #2's LLMNotebookDependencyService
    (when available) to give the LLM each function's upstream/downstream data
    flow as extra context, and the same LLM orchestration pipeline used by
    both -- this service adds no provider-specific behavior, it only asks the
    LLM which functions to expose and rejects anything that isn't a
    well-formed, grounded candidate list. It never touches notebook source.
    """

    def __init__(
        self,
        notebook_analysis_service: LLMNotebookAnalysisService,
        dependency_service: LLMNotebookDependencyService = None,
        orchestration_service=None,
        context_service=None,
        route_request: LLMRouteRequest = None,
    ):
        self._notebook_analysis_service = notebook_analysis_service
        self._dependency_service = dependency_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="api_candidate_detection", required_capabilities=["chat"]
        )
        self._candidates_by_notebook = {}
        self._candidates_by_id = {}
        self._request_counter = 0
        self._candidate_counter = 0

    def _function_context(self, notebook_id: str, function_name: str) -> dict:
        if self._dependency_service is None:
            return {"upstream": [], "downstream": []}

        node_id = f"{notebook_id}::function:{function_name}"
        return {
            "upstream": [dep.source for dep in self._dependency_service.upstream(node_id)],
            "downstream": [dep.target for dep in self._dependency_service.downstream(node_id)],
        }

    def _build_prompt(self, analysis) -> str:
        payload = {
            "notebook_id": analysis.notebook_id,
            "functions": [
                {
                    "name": fn["name"],
                    "cell_index": fn.get("cell_index"),
                    "source": analysis.cells[fn["cell_index"]].source
                    if isinstance(fn.get("cell_index"), int) and 0 <= fn["cell_index"] < len(analysis.cells)
                    else None,
                    "dependencies": self._function_context(analysis.notebook_id, fn["name"]),
                }
                for fn in analysis.functions
            ],
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedCandidateResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("candidates"), list):
            raise MalformedCandidateResponseError(
                "LLM response must be a JSON object with a 'candidates' list"
            )

        candidates = parsed["candidates"]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise MalformedCandidateResponseError("each candidate must be an object")

            for key in ("function_name", "inputs", "outputs", "confidence", "rationale"):
                if key not in candidate:
                    raise MalformedCandidateResponseError(f"candidate missing required field {key!r}")

            if not isinstance(candidate["function_name"], str) or not candidate["function_name"]:
                raise MalformedCandidateResponseError("candidate 'function_name' must be a non-empty string")

            for field in ("inputs", "outputs"):
                if not isinstance(candidate[field], list) or not all(
                    isinstance(item, str) for item in candidate[field]
                ):
                    raise MalformedCandidateResponseError(f"candidate {field!r} must be a list of strings")

            confidence = candidate["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedCandidateResponseError("candidate 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedCandidateResponseError("candidate 'confidence' must be between 0.0 and 1.0")

            if not isinstance(candidate["rationale"], str) or not candidate["rationale"].strip():
                raise MalformedCandidateResponseError("candidate 'rationale' must be a non-empty string")

        return candidates

    def analyze(self, analysis_id: str) -> list:
        analysis = self._notebook_analysis_service.get(analysis_id)
        notebook_id = analysis.notebook_id
        known_functions = {fn["name"] for fn in analysis.functions}

        self._request_counter += 1
        request_id = f"api-candidates-{notebook_id}-{self._request_counter}"

        self._context_service.create(request_id, system=ANALYSIS_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(analysis), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedCandidateResponseError(f"LLM request failed: {decision.reason}")

        raw_candidates = self._parse_response(response.content)

        for candidate in raw_candidates:
            if candidate["function_name"] not in known_functions:
                raise UnknownFunctionCandidateError(
                    f"candidate references unknown function {candidate['function_name']!r}"
                )

        created = []
        for candidate in raw_candidates:
            self._candidate_counter += 1
            record = LLMAPICandidate(
                candidate_id=f"candidate-{notebook_id}-{self._candidate_counter}",
                notebook_id=notebook_id,
                function_name=candidate["function_name"],
                inputs=list(candidate["inputs"]),
                outputs=list(candidate["outputs"]),
                confidence=float(candidate["confidence"]),
                rationale=candidate["rationale"],
            )
            created.append(record)
            self._candidates_by_id[record.candidate_id] = record

        self._candidates_by_notebook.setdefault(notebook_id, []).extend(created)
        return created

    def candidates(self, notebook_id: str) -> list:
        return list(self._candidates_by_notebook.get(notebook_id, []))

    def _get(self, candidate_id: str) -> LLMAPICandidate:
        try:
            return self._candidates_by_id[candidate_id]
        except KeyError:
            raise UnknownCandidateError(candidate_id)

    def inputs(self, candidate_id: str) -> list:
        return list(self._get(candidate_id).inputs)

    def outputs(self, candidate_id: str) -> list:
        return list(self._get(candidate_id).outputs)
