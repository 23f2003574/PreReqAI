import json

from backend.generated_code_review import LLMGeneratedCodeReviewService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest

from .models import RISKS, LLMCodeFixSuggestion

FIX_SUGGESTION_SYSTEM_PROMPT = (
    "You are a code-fix suggestion assistant. You are given a generated-code "
    "review's own findings for one compiler job, each already grounded in "
    "real generated output. For each finding that can reasonably be fixed, "
    "propose at most one suggested fix -- you never rewrite or regenerate "
    "the actual source, you only describe the change a human or a later "
    "commit should make. Respond with ONLY a single JSON object -- no "
    "prose, no markdown fencing -- of the form {\"suggestions\": [...]}. "
    "'suggestions' may be an empty list if no finding warrants a fix. Each "
    "suggestion is an object with: 'finding_index' (the exact integer "
    "index, from the given 'findings' list, of the one finding this "
    "suggestion addresses -- never invented), 'change' (a concise, "
    "concrete description of what should change), 'rationale' (why this "
    "change addresses the finding), 'confidence' (a number between 0.0 and "
    "1.0), and 'risk' (one of LOW, MEDIUM, HIGH, for how risky applying "
    "this change would be). This is advisory only -- never propose editing "
    "the generated output, the compiler, or anything upstream of it, and "
    "never assume a suggestion has been applied."
)


class MalformedFixSuggestionResponseError(ValueError):
    """Raised when the LLM's fix-suggestion response isn't well-formed."""


class UnsupportedSuggestionError(ValueError):
    """Raised when a proposed suggestion doesn't cite a real finding of the review."""


class UnknownSuggestionError(KeyError):
    """Raised when validate() is called for a suggestion_id that was never generated."""


class LLMCodeFixSuggestionService:
    """Turns Commit #1 LLMGeneratedCodeReview findings into reviewable, advisory fixes.

    Reuses Commit #1's LLMGeneratedCodeReviewService.findings() as the sole
    source of what may be suggested against -- suggest() never re-derives or
    re-reviews generated output itself, and a review with no findings never
    reaches the LLM at all. The LLM (same orchestration pipeline used
    throughout) is only asked to propose a change/rationale/risk per
    finding, and every suggestion it proposes must cite one of that
    review's own findings by index; a finding_index outside that range is
    rejected as unsupported, never silently dropped or guessed at. This
    service never generates or applies replacement source -- it is not a
    parallel code-generation pipeline -- and suggest()/validate() never
    mutate the review, its findings, the compiler output, or anything
    upstream of it.
    """

    def __init__(
        self,
        review_service: LLMGeneratedCodeReviewService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._review_service = review_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="code_fix_suggestions", required_capabilities=["chat"]
        )
        self._suggestions = {}
        self._suggestions_by_review = {}
        self._finding_index_by_suggestion = {}
        self._request_counter = 0
        self._suggestion_counter = 0

    @staticmethod
    def _build_prompt(review_id: str, findings: list) -> str:
        payload = {
            "review_id": review_id,
            "findings": [{"finding_index": index, **finding} for index, finding in enumerate(findings)],
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str, num_findings: int) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedFixSuggestionResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("suggestions"), list):
            raise MalformedFixSuggestionResponseError(
                "LLM response must be a JSON object with a 'suggestions' list"
            )

        suggestions = parsed["suggestions"]
        for suggestion in suggestions:
            if not isinstance(suggestion, dict):
                raise MalformedFixSuggestionResponseError("each suggestion must be an object")
            for key in ("finding_index", "change", "rationale", "confidence", "risk"):
                if key not in suggestion:
                    raise MalformedFixSuggestionResponseError(f"suggestion missing required field {key!r}")

            finding_index = suggestion["finding_index"]
            if isinstance(finding_index, bool) or not isinstance(finding_index, int):
                raise MalformedFixSuggestionResponseError("suggestion 'finding_index' must be an integer")
            if not (0 <= finding_index < num_findings):
                raise UnsupportedSuggestionError(
                    f"suggestion references finding_index {finding_index}, which is not one of "
                    "this review's findings"
                )

            if not isinstance(suggestion["change"], str) or not suggestion["change"].strip():
                raise MalformedFixSuggestionResponseError("suggestion 'change' must be a non-empty string")
            if not isinstance(suggestion["rationale"], str) or not suggestion["rationale"].strip():
                raise MalformedFixSuggestionResponseError("suggestion 'rationale' must be a non-empty string")

            confidence = suggestion["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedFixSuggestionResponseError("suggestion 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedFixSuggestionResponseError("suggestion 'confidence' must be between 0.0 and 1.0")

            if suggestion["risk"] not in RISKS:
                raise MalformedFixSuggestionResponseError(f"suggestion 'risk' must be one of {sorted(RISKS)}")

        return suggestions

    def suggest(self, review_id: str) -> list:
        review_findings = self._review_service.findings(review_id)
        if not review_findings:
            return []

        self._request_counter += 1
        request_id = f"fix-suggestions-{review_id}-{self._request_counter}"

        self._context_service.create(request_id, system=FIX_SUGGESTION_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(review_id, review_findings), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedFixSuggestionResponseError(f"LLM request failed: {decision.reason}")

        raw_suggestions = self._parse_response(response.content, len(review_findings))

        created = []
        for raw in raw_suggestions:
            finding = review_findings[raw["finding_index"]]

            self._suggestion_counter += 1
            suggestion = LLMCodeFixSuggestion(
                suggestion_id=f"fix-{review_id}-{self._suggestion_counter}",
                review_id=review_id,
                target=finding["location"],
                change=raw["change"],
                rationale=raw["rationale"],
                confidence=float(raw["confidence"]),
                risk=raw["risk"],
            )
            self._suggestions[suggestion.suggestion_id] = suggestion
            self._finding_index_by_suggestion[suggestion.suggestion_id] = raw["finding_index"]
            created.append(suggestion)

        self._suggestions_by_review.setdefault(review_id, []).extend(created)
        return created

    def _get(self, suggestion_id: str) -> LLMCodeFixSuggestion:
        try:
            return self._suggestions[suggestion_id]
        except KeyError:
            raise UnknownSuggestionError(suggestion_id)

    def validate(self, suggestion_id: str) -> bool:
        suggestion = self._get(suggestion_id)

        if suggestion.risk not in RISKS:
            return False
        if not (0.0 <= suggestion.confidence <= 1.0):
            return False
        if not suggestion.change.strip() or not suggestion.rationale.strip():
            return False

        finding_index = self._finding_index_by_suggestion[suggestion_id]
        current_findings = self._review_service.findings(suggestion.review_id)
        if finding_index >= len(current_findings):
            return False

        return current_findings[finding_index]["location"] == suggestion.target

    def suggestions(self, review_id: str) -> list:
        return list(self._suggestions_by_review.get(review_id, []))

    def get(self, suggestion_id: str) -> LLMCodeFixSuggestion:
        return self._get(suggestion_id)
