import json

from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureRecommendation, LLMAPIExposureService
from backend.input_schema import LLMInputSchemaService, UnknownSchemaError
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.output_schema import STRUCTURED_TYPES, LLMOutputSchemaService, UnknownOutputSchemaError

from .models import APPROVED, REJECTED, LLMAPISchemaReview


class MissingCandidateError(ValueError):
    """Raised when review() is called for a recommendation whose function was
    never registered as an API candidate, so it has no compiler-inferred schemas."""


class MissingSchemaError(ValueError):
    """Raised when review() is called before the candidate's input/output
    schemas have actually been inferred by the compiler's own schema services."""


class MalformedReviewResponseError(ValueError):
    """Raised when the LLM's schema review response isn't well-formed."""


class UnknownReviewTargetError(ValueError):
    """Raised when a review finding cites a target that isn't a real field of this schema."""


class UnknownReviewError(KeyError):
    """Raised when findings()/approved() is called before review() for a review_id."""


def _blocking(category: str, target: str, message: str) -> dict:
    return {"category": category, "target": target, "message": message, "blocking": True}


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


REVIEW_SYSTEM_PROMPT = (
    "You are an API schema reviewer performing a final check before a "
    "compiler generates code from an already-inferred request/response "
    "schema. You are given a candidate function's input and output schema "
    "field types. Flag any field whose type is technically valid but too "
    "ambiguous to safely generate an API from -- e.g. an overly generic "
    "type for how the field is actually described, or a type that "
    "conflicts with the endpoint's own method. Respond with ONLY a single "
    "JSON object -- no prose, no markdown fencing -- of the form "
    "{\"findings\": [...], \"confidence\": 0.0}. 'findings' may be an "
    "empty list if the schema looks sound. Each finding is an object "
    "with: 'category' (a short label), 'target' (the exact field name it "
    "concerns, taken only from the ids listed in 'valid_targets'), "
    "'message' (why this is a problem), and 'blocking' (true if "
    "generation must not proceed until fixed, false if advisory). Never "
    "cite a target that isn't in 'valid_targets'. This is a read-only "
    "review -- never propose editing the schema, candidate, or notebook "
    "directly. 'confidence' is a number between 0.0 and 1.0 for the "
    "review as a whole."
)


class LLMAPISchemaReviewService:
    """Uses the LLM to review a Commit #4 recommendation's already-inferred
    compiler schemas (backend.input_schema / backend.output_schema) before
    API generation.

    Reuses LLMAPIExposureService.notebook_id_for() (Commit #4) and
    backend.api_candidates to find the candidate a recommendation's
    function_name actually corresponds to, then reads that candidate's own
    already-inferred LLMInputSchema/LLMOutputSchema -- never a parallel
    schema of its own. Missing/unsupported structure, requiredness, and
    default-vs-type mismatches are checked deterministically first (the
    same GET-with-structured-required conflict backend.compilation_review
    already checks); the LLM (same orchestration pipeline used throughout)
    is only asked for genuinely ambiguous type judgment calls, and every
    finding it proposes must cite a real field. This service is read-only:
    it never writes to the schemas, the candidate, or the notebook.
    """

    def __init__(
        self,
        exposure_service: LLMAPIExposureService,
        api_candidate_service: LLMAPICandidateService,
        input_schema_service: LLMInputSchemaService,
        output_schema_service: LLMOutputSchemaService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._exposure_service = exposure_service
        self._api_candidate_service = api_candidate_service
        self._input_schema_service = input_schema_service
        self._output_schema_service = output_schema_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="api_schema_review", required_capabilities=["chat"]
        )
        self._reviews_by_id = {}
        self._request_counter = 0
        self._review_counter = 0

    @staticmethod
    def _deterministic_findings(recommendation: LLMAPIExposureRecommendation, input_schema, output_schema) -> list:
        findings = []

        if recommendation.method == "GET":
            structured_required = [
                field for field in input_schema.required if input_schema.types[field] in STRUCTURED_TYPES
            ]
            if structured_required:
                findings.append(
                    _blocking(
                        "SCHEMA_CONFLICT",
                        recommendation.function_name,
                        f"GET {recommendation.endpoint_name} has required structured-type input "
                        f"fields that cannot be expressed as query parameters: {structured_required}",
                    )
                )

        for field, default in input_schema.defaults.items():
            if not _matches_type(default, input_schema.types[field]):
                findings.append(
                    _blocking(
                        "AMBIGUOUS_DEFAULT",
                        field,
                        f"field {field!r} has a default value that doesn't match its declared "
                        f"type {input_schema.types[field]!r}",
                    )
                )

        for field, field_type in output_schema.types.items():
            if field_type in STRUCTURED_TYPES and not output_schema.structure.get(field):
                findings.append(
                    _blocking(
                        "UNSUPPORTED_STRUCTURE",
                        field,
                        f"output field {field!r} is a {field_type} with no described structure",
                    )
                )

        return findings

    @staticmethod
    def _build_prompt(recommendation, input_schema, output_schema, valid_targets: set) -> str:
        payload = {
            "function_name": recommendation.function_name,
            "method": recommendation.method,
            "endpoint_name": recommendation.endpoint_name,
            "input": {"types": input_schema.types, "required": input_schema.required},
            "output": {"types": output_schema.types, "nullable": output_schema.nullable},
            "valid_targets": sorted(valid_targets),
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, valid_targets: set) -> tuple:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedReviewResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
            raise MalformedReviewResponseError("LLM response must be a JSON object with a 'findings' list")

        findings = parsed["findings"]
        for finding in findings:
            if not isinstance(finding, dict):
                raise MalformedReviewResponseError("each finding must be an object")
            for key in ("category", "target", "message", "blocking"):
                if key not in finding:
                    raise MalformedReviewResponseError(f"finding missing required field {key!r}")
            if not isinstance(finding["category"], str) or not finding["category"].strip():
                raise MalformedReviewResponseError("finding 'category' must be a non-empty string")
            if not isinstance(finding["message"], str) or not finding["message"].strip():
                raise MalformedReviewResponseError("finding 'message' must be a non-empty string")
            if not isinstance(finding["blocking"], bool):
                raise MalformedReviewResponseError("finding 'blocking' must be a boolean")
            if not isinstance(finding["target"], str) or finding["target"] not in valid_targets:
                raise UnknownReviewTargetError(
                    f"finding target {finding.get('target')!r} is not part of this schema"
                )

        if "confidence" not in parsed:
            raise MalformedReviewResponseError("LLM response missing required field 'confidence'")
        confidence = parsed["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise MalformedReviewResponseError("'confidence' must be a number")
        if not (0.0 <= float(confidence) <= 1.0):
            raise MalformedReviewResponseError("'confidence' must be between 0.0 and 1.0")

        return findings, float(confidence)

    def review(self, recommendation: LLMAPIExposureRecommendation) -> LLMAPISchemaReview:
        notebook_id = self._exposure_service.notebook_id_for(recommendation.recommendation_id)

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

        try:
            input_schema = self._input_schema_service.get(candidate.candidate_id)
            output_schema = self._output_schema_service.get(candidate.candidate_id)
        except (UnknownSchemaError, UnknownOutputSchemaError) as exc:
            raise MissingSchemaError(
                f"candidate {candidate.candidate_id!r} has no fully-inferred input/output schema"
            ) from exc

        findings = self._deterministic_findings(recommendation, input_schema, output_schema)

        valid_targets = set(input_schema.fields) | set(output_schema.fields) | {recommendation.function_name}

        self._request_counter += 1
        request_id = f"schema-review-{recommendation.recommendation_id}-{self._request_counter}"

        self._context_service.create(request_id, system=REVIEW_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(
                type="user",
                content=self._build_prompt(recommendation, input_schema, output_schema, valid_targets),
                priority=1,
            ),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedReviewResponseError(f"LLM request failed: {decision.reason}")

        llm_findings, confidence = self._parse_response(response.content, valid_targets)
        findings.extend(llm_findings)

        status = REJECTED if any(finding["blocking"] for finding in findings) else APPROVED

        self._review_counter += 1
        review = LLMAPISchemaReview(
            review_id=f"schema-review-{recommendation.recommendation_id}-{self._review_counter}",
            function_name=recommendation.function_name,
            findings=findings,
            status=status,
            confidence=confidence,
        )
        self._reviews_by_id[review.review_id] = review
        return review

    def _get(self, review_id: str) -> LLMAPISchemaReview:
        try:
            return self._reviews_by_id[review_id]
        except KeyError:
            raise UnknownReviewError(review_id)

    def findings(self, review_id: str) -> list:
        return list(self._get(review_id).findings)

    def approved(self, review_id: str) -> bool:
        return self._get(review_id).status == APPROVED
