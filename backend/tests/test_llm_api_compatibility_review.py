import dataclasses
import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_compatibility_review import (
    LLMAPICompatibilityService,
    MalformedCompatibilityResponseError,
    MissingCandidateError,
)
from backend.api_exposure_recommendations import LLMAPIExposureService
from backend.api_risk_analysis import LLMAPIRiskService
from backend.api_schema_review import LLMAPISchemaReviewService
from backend.api_security_review import LLMAPISecurityService
from backend.api_test_generation import LLMAPITestGenerationService
from backend.input_schema import LLMInputSchemaService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_api_intent import LLMNotebookAPIIntent
from backend.notebook_dependencies import LLMNotebookDependencyService
from backend.output_schema import LLMOutputSchemaService
from backend.test_generation import LLMTestGenerationService


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


def build_env(script):
    config_service = LLMProviderConfigService()
    config_service.register(
        LLMProviderConfig(provider="openai", model="gpt-4o", api_key_ref="OPENAI_KEY", enabled=True)
    )

    routing_service = LLMModelRoutingService(config_service)
    routing_service.register_capability_profile(
        "openai", ProviderCapabilityProfile(capabilities={"chat"}, cost=0.01, latency=1.0)
    )

    context_service = LLMContextService()
    orchestration_service = LLMRequestOrchestrationService(
        context_service=context_service,
        routing_service=routing_service,
        providers={"openai": ScriptedProvider(script)},
    )

    notebook_analysis_service = LLMNotebookAnalysisService(orchestration_service, context_service)
    api_candidate_service = LLMAPICandidateService(
        notebook_analysis_service, orchestration_service=orchestration_service, context_service=context_service
    )
    input_schema_service = LLMInputSchemaService(
        api_candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    output_schema_service = LLMOutputSchemaService(
        api_candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    test_generation_service = LLMTestGenerationService(
        api_candidate_service, input_schema_service, output_schema_service, orchestration_service, context_service
    )
    dependency_service = LLMNotebookDependencyService(notebook_analysis_service, orchestration_service, context_service)
    exposure_service = LLMAPIExposureService(notebook_analysis_service, orchestration_service, context_service)
    schema_review_service = LLMAPISchemaReviewService(
        exposure_service,
        api_candidate_service,
        input_schema_service,
        output_schema_service,
        orchestration_service,
        context_service,
    )
    api_test_service = LLMAPITestGenerationService(
        exposure_service, schema_review_service, api_candidate_service, test_generation_service
    )
    risk_service = LLMAPIRiskService(
        exposure_service,
        schema_review_service,
        api_candidate_service,
        notebook_analysis_service,
        dependency_service,
        api_test_service,
        orchestration_service,
        context_service,
    )
    security_service = LLMAPISecurityService(
        exposure_service,
        schema_review_service,
        api_candidate_service,
        notebook_analysis_service,
        dependency_service,
        orchestration_service,
        context_service,
    )
    compatibility_service = LLMAPICompatibilityService(
        exposure_service,
        schema_review_service,
        risk_service,
        security_service,
        api_candidate_service,
        input_schema_service,
        output_schema_service,
        orchestration_service,
        context_service,
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "dependency": dependency_service,
        "exposure": exposure_service,
        "review": schema_review_service,
        "risk": risk_service,
        "security": security_service,
        "compatibility": compatibility_service,
    }


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def add(a, b):\n    return {'sum': a + b}"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "add", "cell_index": 1}], "dependencies": []}
)
CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "add",
                "inputs": ["a", "b"],
                "outputs": ["sum"],
                "confidence": 0.9,
                "rationale": "Pure numeric function.",
            }
        ]
    }
)
INPUT_SCHEMA_RESPONSE = json.dumps(
    {
        "fields": [
            {"name": "a", "type": "int", "constraints": {}, "ambiguous": False},
            {"name": "b", "type": "int", "constraints": {}, "ambiguous": False},
        ]
    }
)
OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "sum", "type": "int", "nullable": False, "structure": {}, "contradictory": False}]}
)
EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "add",
                "endpoint_name": "/add",
                "method": "POST",
                "rationale": "Pure arithmetic function.",
                "confidence": 0.85,
            }
        ]
    }
)
EMPTY_REVIEW_RESPONSE = json.dumps({"findings": [], "confidence": 0.9})
EMPTY_COMPATIBILITY_RESPONSE = json.dumps({"findings": [], "confidence": 0.9})
RISK_DEPENDENCY_CRITICAL_RESPONSE = json.dumps(
    {
        "findings": [
            {
                "category": "DEPENDENCY",
                "severity": "CRITICAL",
                "evidence": "endpoint depends on an unstable, unversioned external service.",
                "confidence": 0.6,
            }
        ]
    }
)


def _confident_intent():
    return LLMNotebookAPIIntent(
        notebook_id="nb-1",
        operations=[{"operation": "expose add", "function": "add", "ambiguous": False}],
        candidate_functions=["add"],
        requested_exposure="PUBLIC",
        constraints=[],
        confidence=0.8,
    )


def _register_candidate(env):
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    return analysis, candidate


def _approved_recommendation(env):
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)
    return recommendation


def test_compatible_recommendation_passes_cleanly():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(EMPTY_COMPATIBILITY_RESPONSE),
        ]
    )
    recommendation = _approved_recommendation(env)

    review = env["compatibility"].review(recommendation)

    assert review.endpoint == "POST /add"
    assert review.compatible is True
    assert review.findings == []
    assert env["compatibility"].compatible("POST /add") is True
    assert env["compatibility"].findings("POST /add") == []


def test_unsupported_endpoint_pattern_is_rejected():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(EMPTY_COMPATIBILITY_RESPONSE),
        ]
    )
    recommendation = _approved_recommendation(env)
    unsupported = dataclasses.replace(recommendation, method="TRACE")

    review = env["compatibility"].review(unsupported)

    assert review.compatible is False
    categories = {f["category"] for f in review.findings}
    assert "UNSUPPORTED_METHOD" in categories
    assert all(f["blocking"] for f in review.findings if f["category"] == "UNSUPPORTED_METHOD")


def test_schema_incompatibility_blocks_when_never_reviewed():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_COMPATIBILITY_RESPONSE),
        ]
    )
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    # Deliberately never schema-reviewed.

    review = env["compatibility"].review(recommendation)

    assert review.compatible is False
    categories = {f["category"] for f in review.findings}
    assert "SCHEMA_INCOMPATIBILITY" in categories


def test_dependency_incompatibility_from_risk_analysis_blocks():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(RISK_DEPENDENCY_CRITICAL_RESPONSE),
            make_response(EMPTY_COMPATIBILITY_RESPONSE),
        ]
    )
    recommendation = _approved_recommendation(env)
    env["risk"].analyze(recommendation)

    review = env["compatibility"].review(recommendation)

    assert review.compatible is False
    dependency_findings = [f for f in review.findings if f["category"] == "DEPENDENCY_INCOMPATIBILITY"]
    assert dependency_findings and all(f["blocking"] for f in dependency_findings)


def test_blocking_finding_is_reflected_in_findings_and_compatible_accessors():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_COMPATIBILITY_RESPONSE),
        ]
    )
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    # Never reviewed -> SCHEMA_INCOMPATIBILITY blocking finding.

    review = env["compatibility"].review(recommendation)

    assert env["compatibility"].compatible("POST /add") is False
    assert env["compatibility"].findings("POST /add") == review.findings
    assert env["compatibility"].compatible("GET /never-reviewed") is True
    assert env["compatibility"].findings("GET /never-reviewed") == []


def test_malformed_llm_response_is_rejected():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response("not json"),
        ]
    )
    recommendation = _approved_recommendation(env)

    with pytest.raises(MalformedCompatibilityResponseError):
        env["compatibility"].review(recommendation)


def test_compiler_integration_uses_real_endpoint_methods_and_missing_candidate():
    env = build_env([make_response(ANALYSIS_RESPONSE), make_response(EXPOSURE_RESPONSE)])
    env["notebook_analysis"].analyze(NOTEBOOK)
    # "add" exists in the notebook's own analysis but was never registered as an API candidate.
    [recommendation] = env["exposure"].recommend(_confident_intent())

    with pytest.raises(MissingCandidateError):
        env["compatibility"].review(recommendation)
