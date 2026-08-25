import json

from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureRecommendation, LLMAPIExposureService
from backend.api_risk_analysis import LLMAPIRiskService
from backend.api_schema_review import APPROVED, LLMAPISchemaReviewService, UnknownReviewError
from backend.input_schema import LLMInputSchemaService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.output_schema import LLMOutputSchemaService

from .models import CATEGORIES, HIGH, IMPACT_LEVELS, LLMAPIOptimization


class SchemaNotApprovedError(ValueError):
    """Raised when analyze() is called for a recommendation whose Commit #5
    schema review was never performed, or wasn't APPROVED."""


class RiskConflictError(ValueError):
    """Raised when analyze()/validate() is called for an endpoint that has an
    unresolved Commit #8 blocking risk finding."""


class MissingCandidateError(ValueError):
    """Raised when analyze() is called for a recommendation whose function was
    never registered as an API candidate."""


class MalformedOptimizationResponseError(ValueError):
    """Raised when the LLM's optimization response isn't well-formed."""


class UnknownOptimizationError(KeyError):
    """Raised when validate() is called for an optimization_id this service never produced."""


OPTIMIZATION_SYSTEM_PROMPT = (
    "You are a performance and maintainability optimization assistant "
    "reviewing an approved API recommendation before it is compiled. You "
    "are given the function's source and its already-inferred input/output "
    "schema. Suggest concrete, evidence-backed optimizations -- never "
    "propose a change that would alter behavior, and never rewrite the "
    "source yourself. Respond with ONLY a single JSON object -- no prose, "
    "no markdown fencing -- of the form {\"optimizations\": [...]}. "
    "'optimizations' may be an empty list if nothing meaningful stands "
    "out. Each optimization is an object with: 'category' (one of "
    "COMPUTE, IO, DEPENDENCY, SCHEMA, CODE), 'recommendation' (a short, "
    "specific description of the change), 'rationale' (the concrete "
    "evidence or reasoning for the claimed improvement -- never leave "
    "this empty), 'expected_impact' (one of LOW, MEDIUM, HIGH), and "
    "'confidence' (a number between 0.0 and 1.0)."
)


class LLMAPIOptimizationService:
    """Suggests, but never applies, performance/maintainability optimizations
    for an approved, risk-clear Commit #4 recommendation.

    Reuses LLMAPISchemaReviewService.review_for() (Commit #5) and
    LLMAPIRiskService.blocking() (Commit #8) as the sole gates: analyze()
    never runs for a recommendation whose schema isn't APPROVED, or whose
    endpoint has an unresolved blocking risk finding -- optimizing
    something with a known critical risk is premature. Every optimization
    the LLM proposes must include non-empty rationale evidence; anything
    else is rejected. Like every generator/validator throughout this
    codebase, this service never executes or mutates notebook source or
    generated API code -- it only ever proposes what a human might choose
    to apply.
    """

    def __init__(
        self,
        exposure_service: LLMAPIExposureService,
        schema_review_service: LLMAPISchemaReviewService,
        risk_service: LLMAPIRiskService,
        api_candidate_service: LLMAPICandidateService,
        notebook_analysis_service: LLMNotebookAnalysisService,
        input_schema_service: LLMInputSchemaService,
        output_schema_service: LLMOutputSchemaService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._exposure_service = exposure_service
        self._schema_review_service = schema_review_service
        self._risk_service = risk_service
        self._api_candidate_service = api_candidate_service
        self._notebook_analysis_service = notebook_analysis_service
        self._input_schema_service = input_schema_service
        self._output_schema_service = output_schema_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="api_optimization_recommendation", required_capabilities=["chat"]
        )
        self._optimizations_by_id = {}
        self._optimizations_by_endpoint = {}
        self._request_counter = 0
        self._optimization_counter = 0

    def _candidate_for(self, recommendation: LLMAPIExposureRecommendation, notebook_id: str):
        candidate = next(
            (
                c
                for c in self._api_candidate_service.candidates(notebook_id)
                if c.function_name == recommendation.function_name
            ),
            None,
        )
        if candidate is None:
            raise MissingCandidateError(
                f"function {recommendation.function_name!r} was never registered as an API candidate"
            )
        return candidate

    @staticmethod
    def _build_prompt(recommendation: LLMAPIExposureRecommendation, source: str, input_schema, output_schema) -> str:
        payload = {
            "function_name": recommendation.function_name,
            "method": recommendation.method,
            "endpoint_name": recommendation.endpoint_name,
            "source": source,
            "input": {"types": input_schema.types, "required": input_schema.required},
            "output": {"types": output_schema.types, "nullable": output_schema.nullable},
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedOptimizationResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("optimizations"), list):
            raise MalformedOptimizationResponseError(
                "LLM response must be a JSON object with an 'optimizations' list"
            )

        optimizations = parsed["optimizations"]
        for optimization in optimizations:
            if not isinstance(optimization, dict):
                raise MalformedOptimizationResponseError("each optimization must be an object")

            for key in ("category", "recommendation", "rationale", "expected_impact", "confidence"):
                if key not in optimization:
                    raise MalformedOptimizationResponseError(f"optimization missing required field {key!r}")

            if optimization["category"] not in CATEGORIES:
                raise MalformedOptimizationResponseError(
                    f"optimization 'category' must be one of {sorted(CATEGORIES)}"
                )
            if not isinstance(optimization["recommendation"], str) or not optimization["recommendation"].strip():
                raise MalformedOptimizationResponseError(
                    "optimization 'recommendation' must be a non-empty string"
                )
            if not isinstance(optimization["rationale"], str) or not optimization["rationale"].strip():
                raise MalformedOptimizationResponseError(
                    "optimization 'rationale' must be non-empty evidence for the claimed improvement"
                )
            if optimization["expected_impact"] not in IMPACT_LEVELS:
                raise MalformedOptimizationResponseError(
                    f"optimization 'expected_impact' must be one of {sorted(IMPACT_LEVELS)}"
                )

            confidence = optimization["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedOptimizationResponseError("optimization 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedOptimizationResponseError("optimization 'confidence' must be between 0.0 and 1.0")

        return optimizations

    def analyze(self, recommendation: LLMAPIExposureRecommendation) -> list:
        try:
            review = self._schema_review_service.review_for(recommendation.recommendation_id)
        except UnknownReviewError as exc:
            raise SchemaNotApprovedError(
                f"recommendation {recommendation.recommendation_id!r} has not been schema-reviewed"
            ) from exc

        if review.status != APPROVED:
            raise SchemaNotApprovedError(
                f"recommendation {recommendation.recommendation_id!r} has a {review.status} schema review"
            )

        endpoint = f"{recommendation.method} {recommendation.endpoint_name}"
        if self._risk_service.blocking(endpoint):
            raise RiskConflictError(
                f"endpoint {endpoint!r} has an unresolved blocking risk finding; resolve it before optimizing"
            )

        notebook_id = self._exposure_service.notebook_id_for(recommendation.recommendation_id)
        candidate = self._candidate_for(recommendation, notebook_id)

        analysis = self._notebook_analysis_service.get_by_notebook(notebook_id)
        function = next((fn for fn in analysis.functions if fn["name"] == recommendation.function_name), None)
        source = analysis.cells[function["cell_index"]].source if function else ""

        input_schema = self._input_schema_service.get(candidate.candidate_id)
        output_schema = self._output_schema_service.get(candidate.candidate_id)

        self._request_counter += 1
        request_id = f"api-optimization-{recommendation.recommendation_id}-{self._request_counter}"

        self._context_service.create(request_id, system=OPTIMIZATION_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(
                type="user",
                content=self._build_prompt(recommendation, source, input_schema, output_schema),
                priority=1,
            ),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedOptimizationResponseError(f"LLM request failed: {decision.reason}")

        raw_optimizations = self._parse_response(response.content)

        created = []
        for optimization in raw_optimizations:
            self._optimization_counter += 1
            record = LLMAPIOptimization(
                optimization_id=f"api-optimization-{recommendation.recommendation_id}-{self._optimization_counter}",
                endpoint=endpoint,
                category=optimization["category"],
                recommendation=optimization["recommendation"],
                rationale=optimization["rationale"],
                expected_impact=optimization["expected_impact"],
                confidence=float(optimization["confidence"]),
            )
            created.append(record)
            self._optimizations_by_id[record.optimization_id] = record

        self._optimizations_by_endpoint.setdefault(endpoint, []).extend(created)
        return created

    def validate(self, optimization_id: str) -> bool:
        try:
            optimization = self._optimizations_by_id[optimization_id]
        except KeyError:
            raise UnknownOptimizationError(optimization_id)

        if self._risk_service.blocking(optimization.endpoint):
            raise RiskConflictError(
                f"optimization {optimization_id!r} conflicts with a blocking risk finding for "
                f"{optimization.endpoint!r}"
            )

        return True

    def high_impact(self, endpoint: str) -> list:
        return [
            optimization
            for optimization in self._optimizations_by_endpoint.get(endpoint, [])
            if optimization.expected_impact == HIGH
        ]
