import copy
import json

import pytest

from backend.compilation_execution import CompilerJobResult
from backend.generated_code_review import (
    InvalidGeneratedOutputError,
    LLMGeneratedCodeReviewService,
    MalformedGeneratedCodeReviewResponseError,
    UnknownReviewError,
)
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


def build_service(script):
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

    return LLMGeneratedCodeReviewService(orchestration_service, context_service), provider


EMPTY_FINDINGS_RESPONSE = json.dumps({"findings": [], "confidence": 0.95})


def test_review_generation_with_no_further_findings():
    service, provider = build_service([make_response(EMPTY_FINDINGS_RESPONSE)])
    generated_output = CompilerJobResult(
        job_id="job-1", status="SUCCEEDED", output={"endpoint": "/add", "source": "def add(a, b):\n    return a + b"}
    )

    review = service.review(generated_output)

    assert review.target == "job-1"
    assert review.status == "APPROVED"
    assert review.severity == "INFO"
    assert review.confidence == 0.95
    assert review.findings == []
    assert provider.calls == 1


def test_llm_finding_must_reference_real_location():
    llm_response = json.dumps(
        {
            "findings": [
                {
                    "category": "QUALITY",
                    "location": "source",
                    "severity": "WARNING",
                    "message": "generated function has no docstring",
                }
            ],
            "confidence": 0.8,
        }
    )
    service, _ = build_service([make_response(llm_response)])
    generated_output = CompilerJobResult(
        job_id="job-2", status="SUCCEEDED", output={"source": "def add(a, b):\n    return a + b"}
    )

    review = service.review(generated_output)

    assert len(review.findings) == 1
    assert review.findings[0]["location"] == "source"
    assert review.status == "APPROVED"


def test_finding_validation_rejects_fabricated_location():
    llm_response = json.dumps(
        {
            "findings": [
                {
                    "category": "QUALITY",
                    "location": "not_a_real_key",
                    "severity": "WARNING",
                    "message": "made up issue",
                }
            ],
            "confidence": 0.8,
        }
    )
    service, _ = build_service([make_response(llm_response)])
    generated_output = CompilerJobResult(job_id="job-3", status="SUCCEEDED", output={"source": "def add(): pass"})

    with pytest.raises(MalformedGeneratedCodeReviewResponseError):
        service.review(generated_output)


def test_blocking_detection_from_deterministic_security_scan():
    service, provider = build_service([make_response(EMPTY_FINDINGS_RESPONSE)])
    generated_output = CompilerJobResult(
        job_id="job-4",
        status="SUCCEEDED",
        output={"source": "def add(a, b):\n    api_key = 'sk-abcdefghijklmnop'\n    return a + b"},
    )

    review = service.review(generated_output)

    assert review.status == "REJECTED"
    assert review.severity == "CRITICAL"
    assert service.blocking(review.review_id) is True
    assert any(finding["category"] == "SECURITY" for finding in service.findings(review.review_id))
    assert provider.calls == 1


def test_failed_compilation_is_a_blocking_finding_without_an_llm_call():
    service, provider = build_service([make_response(EMPTY_FINDINGS_RESPONSE)])
    generated_output = CompilerJobResult(job_id="job-5", status="FAILED", output={})

    review = service.review(generated_output)

    assert review.status == "REJECTED"
    assert service.blocking(review.review_id) is True
    assert review.findings[0]["location"] == "job-5"
    assert provider.calls == 0


def test_empty_output_is_a_blocking_finding_without_an_llm_call():
    service, provider = build_service([make_response(EMPTY_FINDINGS_RESPONSE)])
    generated_output = CompilerJobResult(job_id="job-6", status="SUCCEEDED", output={})

    review = service.review(generated_output)

    assert review.status == "REJECTED"
    assert service.blocking(review.review_id) is True
    assert provider.calls == 0


@pytest.mark.parametrize(
    "bad_output",
    [
        {"job_id": "job-1", "status": "SUCCEEDED", "output": {}},
        CompilerJobResult(job_id="", status="SUCCEEDED"),
        CompilerJobResult(job_id="job-1", status="DONE"),
        CompilerJobResult(job_id="job-1", status="SUCCEEDED", output="not-a-dict"),
    ],
)
def test_malformed_generated_output_is_rejected(bad_output):
    service, _ = build_service([make_response(EMPTY_FINDINGS_RESPONSE)])

    with pytest.raises(InvalidGeneratedOutputError):
        service.review(bad_output)


@pytest.mark.parametrize(
    "malformed_response",
    [
        "not json",
        json.dumps({"findings": "not-a-list"}),
        json.dumps({"findings": [{"category": "NOT_REAL", "location": "source", "severity": "INFO", "message": "x"}]}),
        json.dumps({"findings": [{"category": "QUALITY", "location": "source", "severity": "NOT_REAL", "message": "x"}]}),
        json.dumps({"findings": [{"category": "QUALITY", "location": "source", "severity": "INFO", "message": ""}]}),
        json.dumps({"findings": []}),
        json.dumps({"findings": [], "confidence": 2.0}),
    ],
)
def test_malformed_llm_response_is_rejected(malformed_response):
    service, _ = build_service([make_response(malformed_response)])
    generated_output = CompilerJobResult(job_id="job-7", status="SUCCEEDED", output={"source": "def add(): pass"})

    with pytest.raises(MalformedGeneratedCodeReviewResponseError):
        service.review(generated_output)


def test_unknown_review_id_raises():
    service, _ = build_service([make_response(EMPTY_FINDINGS_RESPONSE)])

    with pytest.raises(UnknownReviewError):
        service.findings("no-such-review")
    with pytest.raises(UnknownReviewError):
        service.blocking("no-such-review")


def test_generated_output_integration_with_nested_structure():
    service, _ = build_service(
        [
            make_response(
                json.dumps(
                    {
                        "findings": [
                            {
                                "category": "CORRECTNESS",
                                "location": "endpoints[0].path",
                                "severity": "ERROR",
                                "message": "path does not match the plan's declared route",
                            }
                        ],
                        "confidence": 0.7,
                    }
                )
            )
        ]
    )
    generated_output = CompilerJobResult(
        job_id="job-8",
        status="SUCCEEDED",
        output={"endpoints": [{"path": "/add", "method": "POST"}]},
    )

    review = service.review(generated_output)

    assert review.findings[0]["location"] == "endpoints[0].path"
    assert review.status == "APPROVED"
    assert review.severity == "ERROR"


def test_source_immutability():
    service, _ = build_service([make_response(EMPTY_FINDINGS_RESPONSE)])
    output = {"source": "def add(a, b):\n    return a + b", "nested": {"a": 1}}
    original = copy.deepcopy(output)
    generated_output = CompilerJobResult(job_id="job-9", status="SUCCEEDED", output=output)

    service.review(generated_output)

    assert generated_output.output == original
