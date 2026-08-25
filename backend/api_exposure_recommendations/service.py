import json

from backend.compilation_plan import ENDPOINT_METHODS
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_api_intent import LLMNotebookAPIIntent

from .models import LLMAPIExposureRecommendation


class MalformedRecommendationResponseError(ValueError):
    """Raised when the LLM's exposure recommendation response isn't well-formed."""


class UnknownExposureFunctionError(ValueError):
    """Raised when a recommendation references a function that either doesn't
    exist in the notebook's analysis or wasn't part of the intent's confident mapping."""


class UnsupportedMethodError(ValueError):
    """Raised when a recommendation uses an HTTP method the compiler doesn't support."""


class UnknownRecommendationError(KeyError):
    """Raised when validate() is called for a recommendation this service never produced."""


EXPOSURE_SYSTEM_PROMPT = (
    "You are an API exposure planning assistant. Given a list of notebook "
    "functions the user has confidently expressed intent to expose, "
    "recommend a REST endpoint for each. Respond with ONLY a single JSON "
    "object -- no prose, no markdown fencing -- of the form "
    "{\"recommendations\": [...]}. There must be exactly one entry per "
    "given function, each an object with: 'function_name' (must exactly "
    "match one of the given function names), 'endpoint_name' (a URL path "
    "starting with '/'), 'method' (one of GET, POST, PUT, PATCH, DELETE), "
    "'rationale' (a short reason for this endpoint shape), and "
    "'confidence' (a number between 0.0 and 1.0)."
)


class LLMAPIExposureService:
    """Turns a Commit #3 intent into concrete, reviewable endpoint recommendations.

    Reuses backend.notebook_analysis for the ground-truth set of functions
    a recommendation must reference, and
    backend.compilation_plan.ENDPOINT_METHODS -- the same HTTP methods the
    existing deterministic compiler already supports -- to reject anything
    it couldn't act on. Only intent operations Commit #3 already mapped to
    a real function with confidence (ambiguous=False) are ever considered;
    an ambiguous operation is skipped here, never guessed. This service
    never generates, edits, or touches generated API code or the compiler
    itself -- it only ever proposes what a human might choose to compile.
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
            task="api_exposure_recommendation", required_capabilities=["chat"]
        )
        self._recommendations_by_notebook = {}
        self._notebook_by_recommendation = {}
        self._request_counter = 0
        self._recommendation_counter = 0

    @staticmethod
    def _mappable_functions(intent: LLMNotebookAPIIntent, known_functions: set) -> list:
        confident = {
            operation["function"]
            for operation in intent.operations
            if not operation["ambiguous"] and operation["function"]
        }
        return sorted(confident & known_functions)

    @staticmethod
    def _parse_response(raw_content: str, mappable_functions: set) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedRecommendationResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("recommendations"), list):
            raise MalformedRecommendationResponseError(
                "LLM response must be a JSON object with a 'recommendations' list"
            )

        recommendations = parsed["recommendations"]
        seen = set()
        for recommendation in recommendations:
            if not isinstance(recommendation, dict):
                raise MalformedRecommendationResponseError("each recommendation must be an object")

            for key in ("function_name", "endpoint_name", "method", "rationale", "confidence"):
                if key not in recommendation:
                    raise MalformedRecommendationResponseError(f"recommendation missing required field {key!r}")

            if recommendation["function_name"] not in mappable_functions:
                raise UnknownExposureFunctionError(
                    f"recommendation references function {recommendation['function_name']!r}, "
                    "which was not part of the confidently-mapped intent"
                )
            if recommendation["method"] not in ENDPOINT_METHODS:
                raise UnsupportedMethodError(
                    f"recommendation uses unsupported method {recommendation['method']!r}; "
                    f"must be one of {sorted(ENDPOINT_METHODS)}"
                )
            if not isinstance(recommendation["endpoint_name"], str) or not recommendation[
                "endpoint_name"
            ].startswith("/"):
                raise MalformedRecommendationResponseError(
                    "recommendation 'endpoint_name' must be a string starting with '/'"
                )
            if not isinstance(recommendation["rationale"], str) or not recommendation["rationale"].strip():
                raise MalformedRecommendationResponseError(
                    "recommendation 'rationale' must be a non-empty string"
                )

            confidence = recommendation["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedRecommendationResponseError("recommendation 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedRecommendationResponseError(
                    "recommendation 'confidence' must be between 0.0 and 1.0"
                )

            seen.add(recommendation["function_name"])

        missing = mappable_functions - seen
        if missing:
            raise MalformedRecommendationResponseError(
                f"response is missing recommendations for functions: {sorted(missing)}"
            )

        return recommendations

    def recommend(self, intent: LLMNotebookAPIIntent) -> list:
        analysis = self._notebook_analysis_service.get_by_notebook(intent.notebook_id)
        known_functions = {fn["name"] for fn in analysis.functions}

        mappable_functions = self._mappable_functions(intent, known_functions)
        if not mappable_functions:
            return []

        self._request_counter += 1
        request_id = f"api-exposure-{intent.notebook_id}-{self._request_counter}"

        self._context_service.create(request_id, system=EXPOSURE_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=json.dumps({"functions": mappable_functions}), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedRecommendationResponseError(f"LLM request failed: {decision.reason}")

        raw_recommendations = self._parse_response(response.content, set(mappable_functions))

        created = []
        for recommendation in raw_recommendations:
            self._recommendation_counter += 1
            record = LLMAPIExposureRecommendation(
                recommendation_id=f"exposure-{intent.notebook_id}-{self._recommendation_counter}",
                function_name=recommendation["function_name"],
                endpoint_name=recommendation["endpoint_name"],
                method=recommendation["method"],
                rationale=recommendation["rationale"],
                confidence=float(recommendation["confidence"]),
            )
            created.append(record)
            self._notebook_by_recommendation[record.recommendation_id] = intent.notebook_id

        self._recommendations_by_notebook.setdefault(intent.notebook_id, []).extend(created)
        return created

    def validate(self, recommendation: LLMAPIExposureRecommendation) -> bool:
        try:
            notebook_id = self._notebook_by_recommendation[recommendation.recommendation_id]
        except KeyError:
            raise UnknownRecommendationError(recommendation.recommendation_id)

        if recommendation.method not in ENDPOINT_METHODS:
            raise UnsupportedMethodError(
                f"recommendation {recommendation.recommendation_id!r} uses unsupported method "
                f"{recommendation.method!r}"
            )

        analysis = self._notebook_analysis_service.get_by_notebook(notebook_id)
        known_functions = {fn["name"] for fn in analysis.functions}
        if recommendation.function_name not in known_functions:
            raise UnknownExposureFunctionError(
                f"recommendation {recommendation.recommendation_id!r} references a function that "
                f"no longer exists: {recommendation.function_name!r}"
            )

        return True

    def recommendations(self, notebook_id: str) -> list:
        return list(self._recommendations_by_notebook.get(notebook_id, []))
