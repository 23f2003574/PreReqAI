import copy
import json

import pytest

from backend.code_fix_suggestions import (
    LLMCodeFixSuggestionService,
    MalformedFixSuggestionResponseError,
    UnknownSuggestionError,
    UnsupportedSuggestionError,
)
from backend.compilation_execution import CompilerJobResult
from backend.generated_code_review import LLMGeneratedCodeReviewService, UnknownReviewError
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile


class ScriptedProvider(LLMProvider):
    """A real LLMProvider that replays one scripted outcome per call, in order."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = 0

    def models(self):
        return ["gpt-4o"]

    def complete(self, request):
        self.calls += 1
        outcome = self._script[min(self.calls - 1, len(self._script) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def stream(self, request):
        raise NotImplementedError


def make_response(content):
    return LLMResponse(content=content, model="gpt-4o", usage={"total_tokens": 15})


def build_services(script):
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True)
    )

    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )

    context_service = LLMContextService()
    provider = ScriptedProvider(script)
    orchestration_service = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={"openai": provider},
    )

    review_service = LLMGeneratedCodeReviewService(orchestration_service, context_service)
    fix_service = LLMCodeFixSuggestionService(review_service, orchestration_service, context_service)
    return review_service, fix_service, provider


def build_reviewed_job(script, job_id="job-1"):
    """A FAILED compiler job always produces exactly one deterministic
    CRITICAL CORRECTNESS finding without an LLM call, so it's a minimal,
    single-finding review to generate fix suggestions against."""
    review_service, fix_service, provider = build_services(script)
    generated_output = CompilerJobResult(job_id=job_id, status="FAILED", output={})
    review = review_service.review(generated_output)
    return review_service, fix_service, provider, review


ONE_SUGGESTION_RESPONSE = json.dumps(
    {
        "suggestions": [
            {
                "finding_index": 0,
                "change": "Re-run the compiler after fixing the underlying plan issue.",
                "rationale": "The job failed, so there is no successfully generated code yet.",
                "confidence": 0.8,
                "risk": "LOW",
            }
        ]
    }
)


def test_suggestion_generation():
    review_service, fix_service, provider, review = build_reviewed_job([make_response(ONE_SUGGESTION_RESPONSE)])

    suggestions = fix_service.suggest(review.review_id)

    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion.review_id == review.review_id
    assert suggestion.change == "Re-run the compiler after fixing the underlying plan issue."
    assert suggestion.rationale == "The job failed, so there is no successfully generated code yet."
    assert suggestion.confidence == 0.8
    assert suggestion.risk == "LOW"
    assert provider.calls == 1
    assert fix_service.suggestions(review.review_id) == suggestions


def test_finding_mapping():
    review_service, fix_service, provider, review = build_reviewed_job([make_response(ONE_SUGGESTION_RESPONSE)])

    suggestions = fix_service.suggest(review.review_id)

    assert suggestions[0].target == review.findings[0]["location"]
    assert suggestions[0].target == "job-1"


def test_risk_validation():
    bad_risk_response = json.dumps(
        {
            "suggestions": [
                {
                    "finding_index": 0,
                    "change": "Do something.",
                    "rationale": "Because.",
                    "confidence": 0.5,
                    "risk": "SEVERE",
                }
            ]
        }
    )
    review_service, fix_service, provider, review = build_reviewed_job([make_response(bad_risk_response)])

    with pytest.raises(MalformedFixSuggestionResponseError):
        fix_service.suggest(review.review_id)


def test_validate_accepts_a_grounded_suggestion():
    review_service, fix_service, provider, review = build_reviewed_job([make_response(ONE_SUGGESTION_RESPONSE)])
    suggestion = fix_service.suggest(review.review_id)[0]

    assert fix_service.validate(suggestion.suggestion_id) is True


def test_validate_unknown_suggestion_raises():
    review_service, fix_service, provider, review = build_reviewed_job([make_response(ONE_SUGGESTION_RESPONSE)])

    with pytest.raises(UnknownSuggestionError):
        fix_service.validate("no-such-suggestion")


def test_unsupported_suggestion_is_rejected():
    unsupported_response = json.dumps(
        {
            "suggestions": [
                {
                    "finding_index": 5,
                    "change": "Do something.",
                    "rationale": "Because.",
                    "confidence": 0.5,
                    "risk": "LOW",
                }
            ]
        }
    )
    review_service, fix_service, provider, review = build_reviewed_job([make_response(unsupported_response)])

    with pytest.raises(UnsupportedSuggestionError):
        fix_service.suggest(review.review_id)


@pytest.mark.parametrize(
    "malformed_response",
    [
        "not json",
        json.dumps({"suggestions": "not-a-list"}),
        json.dumps({"suggestions": [{"finding_index": 0, "change": "x", "rationale": "y", "confidence": 0.5}]}),
        json.dumps(
            {"suggestions": [{"finding_index": "0", "change": "x", "rationale": "y", "confidence": 0.5, "risk": "LOW"}]}
        ),
        json.dumps({"suggestions": [{"finding_index": 0, "change": "", "rationale": "y", "confidence": 0.5, "risk": "LOW"}]}),
        json.dumps({"suggestions": [{"finding_index": 0, "change": "x", "rationale": "y", "confidence": 2.0, "risk": "LOW"}]}),
    ],
)
def test_malformed_llm_response_is_rejected(malformed_response):
    review_service, fix_service, provider, review = build_reviewed_job([make_response(malformed_response)])

    with pytest.raises(MalformedFixSuggestionResponseError):
        fix_service.suggest(review.review_id)


def test_no_findings_never_calls_llm():
    review_service, fix_service, provider = build_services(
        [make_response(json.dumps({"findings": [], "confidence": 1.0}))]
    )
    generated_output = CompilerJobResult(job_id="job-2", status="SUCCEEDED", output={"source": "def add(): pass"})
    review = review_service.review(generated_output)
    assert review.findings == []

    suggestions = fix_service.suggest(review.review_id)

    assert suggestions == []
    assert provider.calls == 1


def test_unknown_review_id_propagates_commit1_error():
    review_service, fix_service, provider = build_services([make_response(ONE_SUGGESTION_RESPONSE)])

    with pytest.raises(UnknownReviewError):
        fix_service.suggest("no-such-review")


def test_source_immutability():
    review_service, fix_service, provider, review = build_reviewed_job([make_response(ONE_SUGGESTION_RESPONSE)])
    original_findings = copy.deepcopy(review.findings)

    fix_service.suggest(review.review_id)

    assert review.findings == original_findings
