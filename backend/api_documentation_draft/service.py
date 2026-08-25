from backend.api_candidates import LLMAPICandidateService
from backend.api_documentation import LLMAPIDocumentationService, UnknownDocumentationError
from backend.api_exposure_recommendations import LLMAPIExposureRecommendation, LLMAPIExposureService
from backend.api_schema_review import APPROVED, LLMAPISchemaReviewService, UnknownReviewError

from .models import DRAFT, VALIDATED, LLMAPIDocumentationDraft


class SchemaNotApprovedError(ValueError):
    """Raised when generate() is called for a recommendation whose Commit #5
    schema review was never performed, or wasn't APPROVED."""


class MissingCandidateError(ValueError):
    """Raised when generate() is called for a recommendation whose function was
    never registered as an API candidate."""


class UnknownDraftError(KeyError):
    """Raised when get()/validate() is called for a draft_id this service never produced."""


class LLMAPIDocumentationDraftService:
    """Drafts reviewable API documentation for a Commit #4 recommendation once
    Commit #5 has approved its schema.

    Reuses backend.api_documentation.LLMAPIDocumentationService (from the
    original notebook-to-API series) as the sole source of
    parameters/responses/examples -- this service never independently asks
    the LLM to describe a schema or invents an example; it only calls the
    existing, already schema-grounded and example-validated documentation
    service and wraps its result with the recommendation's own endpoint and
    a DRAFT/VALIDATED review lifecycle. Nothing here regenerates OpenAPI
    output or touches the compiler -- it only ever reads what already
    exists.
    """

    def __init__(
        self,
        exposure_service: LLMAPIExposureService,
        schema_review_service: LLMAPISchemaReviewService,
        api_candidate_service: LLMAPICandidateService,
        documentation_service: LLMAPIDocumentationService,
    ):
        self._exposure_service = exposure_service
        self._schema_review_service = schema_review_service
        self._api_candidate_service = api_candidate_service
        self._documentation_service = documentation_service
        self._drafts_by_id = {}
        self._candidate_by_draft = {}
        self._draft_counter = 0

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

    def generate(self, recommendation: LLMAPIExposureRecommendation) -> LLMAPIDocumentationDraft:
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

        try:
            doc = self._documentation_service.get(candidate.candidate_id)
        except UnknownDocumentationError:
            doc = self._documentation_service.generate(candidate.candidate_id)

        self._draft_counter += 1
        draft = LLMAPIDocumentationDraft(
            draft_id=f"doc-draft-{recommendation.recommendation_id}-{self._draft_counter}",
            endpoint=f"{recommendation.method} {recommendation.endpoint_name}",
            summary=doc.summary,
            description=doc.description,
            parameters=doc.parameters,
            responses=doc.response,
            examples=doc.examples,
            status=DRAFT,
        )
        self._drafts_by_id[draft.draft_id] = draft
        self._candidate_by_draft[draft.draft_id] = candidate.candidate_id
        return draft

    def validate(self, draft: LLMAPIDocumentationDraft) -> LLMAPIDocumentationDraft:
        try:
            candidate_id = self._candidate_by_draft[draft.draft_id]
        except KeyError:
            raise UnknownDraftError(draft.draft_id)

        self._documentation_service.validate(candidate_id)

        validated = LLMAPIDocumentationDraft(
            draft_id=draft.draft_id,
            endpoint=draft.endpoint,
            summary=draft.summary,
            description=draft.description,
            parameters=draft.parameters,
            responses=draft.responses,
            examples=draft.examples,
            status=VALIDATED,
        )
        self._drafts_by_id[draft.draft_id] = validated
        return validated

    def get(self, draft_id: str) -> LLMAPIDocumentationDraft:
        try:
            return self._drafts_by_id[draft_id]
        except KeyError:
            raise UnknownDraftError(draft_id)
