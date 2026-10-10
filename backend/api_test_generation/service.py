from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureRecommendation, LLMAPIExposureService
from backend.api_schema_review import APPROVED, LLMAPISchemaReviewService, UnknownReviewError
from backend.test_generation import LLMTestGenerationService

from .models import LLMAPITestCase


class SchemaNotApprovedError(ValueError):
    """Raised when generate() is called for a recommendation whose Commit #5
    schema review was never performed, or wasn't APPROVED."""


class MissingCandidateError(ValueError):
    """Raised when generate() is called for a recommendation whose function was
    never registered as an API candidate."""


class UnknownTestError(KeyError):
    """Raised when validate() is called for a test_id this service never produced."""


class LLMAPITestGenerationService:
    """Generates reviewable API test cases for a Commit #4 recommendation's
    endpoint, once Commit #5 has approved its schema.

    Reuses backend.test_generation.LLMTestGenerationService (from the
    original notebook-to-API series) as the sole source of test data --
    this service never independently asks the LLM for a request/response
    pair or invents VALID/INVALID/EDGE rules of its own; it only calls the
    existing, already schema-grounded test generator and reshapes each
    LLMGeneratedTest into an endpoint-keyed LLMAPITestCase. validate()
    delegates straight to that same service's own validate(), so a test
    case can never be re-checked against anything but the real schemas.
    Nothing here executes a test, an endpoint, or the candidate function.
    """

    def __init__(
        self,
        exposure_service: LLMAPIExposureService,
        schema_review_service: LLMAPISchemaReviewService,
        api_candidate_service: LLMAPICandidateService,
        test_generation_service: LLMTestGenerationService,
    ):
        self._exposure_service = exposure_service
        self._schema_review_service = schema_review_service
        self._api_candidate_service = api_candidate_service
        self._test_generation_service = test_generation_service
        self._tests_by_id = {}
        self._tests_by_endpoint = {}
        self._underlying_test_id_by_test_id = {}
        self._test_counter = 0

    def _candidate_for(self, recommendation: LLMAPIExposureRecommendation):
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
        return candidate

    def generate(self, recommendation: LLMAPIExposureRecommendation) -> list:
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

        candidate = self._candidate_for(recommendation)
        endpoint = f"{recommendation.method} {recommendation.endpoint_name}"

        generated_tests = self._test_generation_service.generate(candidate.candidate_id)

        created = []
        for test in generated_tests:
            self._test_counter += 1
            record = LLMAPITestCase(
                test_id=f"api-test-{recommendation.recommendation_id}-{self._test_counter}",
                endpoint=endpoint,
                scenario=test.scenario,
                request=dict(test.input),
                expected_response=dict(test.expected_output),
                category=test.category,
                confidence=test.confidence,
            )
            created.append(record)
            self._tests_by_id[record.test_id] = record
            self._underlying_test_id_by_test_id[record.test_id] = test.test_id

        self._tests_by_endpoint.setdefault(endpoint, []).extend(created)
        return created

    def validate(self, test_id: str) -> bool:
        try:
            underlying_test_id = self._underlying_test_id_by_test_id[test_id]
        except KeyError:
            raise UnknownTestError(test_id)
        return self._test_generation_service.validate(underlying_test_id)

    def tests(self, endpoint: str) -> list:
        return list(self._tests_by_endpoint.get(endpoint, []))
