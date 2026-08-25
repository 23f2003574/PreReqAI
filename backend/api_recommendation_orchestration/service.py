from datetime import datetime, timezone

from backend.api_compatibility_review import LLMAPICompatibilityService
from backend.api_exposure_recommendations import LLMAPIExposureService
from backend.api_risk_analysis import CRITICAL as RISK_CRITICAL
from backend.api_risk_analysis import LLMAPIRiskService
from backend.api_schema_review import LLMAPISchemaReviewService
from backend.api_security_review import CRITICAL as SECURITY_CRITICAL
from backend.api_security_review import LLMAPISecurityService
from backend.notebook_api_intent import LLMNotebookAPIIntentService, UnknownIntentError

from .models import LLMAPIRecommendationDecision


class MissingAnalysisError(ValueError):
    """Raised when review()/recommend() is called before the notebook has an
    extracted intent (analyze()) or reviewed exposure recommendations (review())."""


class UnknownDecisionError(KeyError):
    """Raised when decision() is called for a notebook_id with no recorded decision."""


def _finding(source: str, endpoint: str, category: str, message: str) -> dict:
    return {"source": source, "endpoint": endpoint, "category": category, "message": message}


class LLMAPIRecommendationOrchestrationService:
    """Unifies Commit #3 intent extraction through Commit #4 exposure
    recommendation, Commit #5 schema review, and the Commit #8/#10/#11
    risk/security/compatibility gates into one deterministic recommendation
    pipeline.

    analyze() only ever calls LLMNotebookAPIIntentService.extract() on an
    already-parsed notebook (backend.notebook_analysis); review() only ever
    calls LLMAPIExposureService.recommend() and LLMAPISchemaReviewService.
    review(); recommend() only ever calls LLMAPIRiskService.analyze(),
    LLMAPISecurityService.analyze(), and LLMAPICompatibilityService.
    review() for every recommendation review() produced, then aggregates
    their own findings into one LLMAPIRecommendationDecision -- approved
    only when nothing any of them reported is blocking (a CRITICAL risk or
    security finding, or a blocking compatibility finding). Nothing here
    reimplements a single check any earlier commit already performs, and
    nothing here mutates notebook source, the schemas, or the compiler.
    """

    def __init__(
        self,
        intent_service: LLMNotebookAPIIntentService,
        exposure_service: LLMAPIExposureService,
        schema_review_service: LLMAPISchemaReviewService,
        risk_service: LLMAPIRiskService,
        security_service: LLMAPISecurityService,
        compatibility_service: LLMAPICompatibilityService,
    ):
        self._intent_service = intent_service
        self._exposure_service = exposure_service
        self._schema_review_service = schema_review_service
        self._risk_service = risk_service
        self._security_service = security_service
        self._compatibility_service = compatibility_service
        self._decisions_by_notebook = {}
        self._decision_counter = 0

    def analyze(self, notebook_id: str):
        """Stage 1: extract intent (Commit #3) from the notebook's already-parsed analysis."""
        return self._intent_service.extract(notebook_id)

    def review(self, notebook_id: str) -> list:
        """Stage 2: turn the extracted intent into exposure recommendations
        (Commit #4) and schema-review each one (Commit #5)."""
        try:
            intent = self._intent_service.get(notebook_id)
        except UnknownIntentError as exc:
            raise MissingAnalysisError(
                f"notebook {notebook_id!r} has not been analyzed; call analyze() first"
            ) from exc

        recommendations = self._exposure_service.recommend(intent)
        for recommendation in recommendations:
            self._schema_review_service.review(recommendation)
        return recommendations

    def recommend(self, notebook_id: str) -> LLMAPIRecommendationDecision:
        """Stage 3: run the risk/security/compatibility gates on every reviewed
        recommendation and produce one deterministic decision."""
        recommendations = self._exposure_service.recommendations(notebook_id)
        if not recommendations:
            raise MissingAnalysisError(
                f"notebook {notebook_id!r} has no reviewed recommendations; call review() first"
            )

        blocking_findings = []
        warnings = []

        for recommendation in recommendations:
            endpoint = f"{recommendation.method} {recommendation.endpoint_name}"

            for finding in self._risk_service.analyze(recommendation):
                bucket = blocking_findings if finding.severity == RISK_CRITICAL else warnings
                bucket.append(_finding("RISK", endpoint, finding.category, finding.evidence))

            for finding in self._security_service.analyze(recommendation):
                bucket = blocking_findings if finding.severity == SECURITY_CRITICAL else warnings
                bucket.append(_finding("SECURITY", endpoint, finding.category, finding.evidence))

            compatibility_review = self._compatibility_service.review(recommendation)
            for finding in compatibility_review.findings:
                bucket = blocking_findings if finding["blocking"] else warnings
                bucket.append(_finding("COMPATIBILITY", endpoint, finding["category"], finding["message"]))

        self._decision_counter += 1
        decision = LLMAPIRecommendationDecision(
            decision_id=f"api-decision-{notebook_id}-{self._decision_counter}",
            notebook_id=notebook_id,
            recommendations=[r.recommendation_id for r in recommendations],
            approved=not blocking_findings,
            blocking_findings=blocking_findings,
            warnings=warnings,
            created_at=datetime.now(timezone.utc),
        )
        self._decisions_by_notebook[notebook_id] = decision
        return decision

    def decision(self, notebook_id: str) -> LLMAPIRecommendationDecision:
        try:
            return self._decisions_by_notebook[notebook_id]
        except KeyError:
            raise UnknownDecisionError(notebook_id)
