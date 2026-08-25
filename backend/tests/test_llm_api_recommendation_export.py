import dataclasses
import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_compatibility_review import LLMAPICompatibilityService
from backend.api_exposure_recommendations import LLMAPIExposureService
from backend.api_recommendation_export import (
    DecisionNotApprovedError,
    LLMAPIRecommendationExportService,
    MalformedDecisionError,
    MalformedExportError,
    UnsupportedFormatError,
)
from backend.api_recommendation_orchestration import LLMAPIRecommendationOrchestrationService
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
from backend.notebook_api_intent import LLMNotebookAPIIntentService
from backend.notebook_dependencies import LLMNotebookDependencyService
from backend.notebook_summary import LLMNotebookSummaryService
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
    summary_service = LLMNotebookSummaryService(notebook_analysis_service, orchestration_service, context_service)
    intent_service = LLMNotebookAPIIntentService(
        notebook_analysis_service, summary_service, orchestration_service, context_service
    )
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
    orchestration = LLMAPIRecommendationOrchestrationService(
        intent_service, exposure_service, schema_review_service, risk_service, security_service, compatibility_service
    )
    export_service = LLMAPIRecommendationExportService(
        exposure_service, api_candidate_service, input_schema_service, output_schema_service
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "orchestration": orchestration,
        "export": export_service,
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
INTENT_RESPONSE = json.dumps(
    {
        "operations": [{"operation": "expose add", "function": "add", "ambiguous": False}],
        "candidate_functions": ["add"],
        "requested_exposure": "PUBLIC",
        "constraints": [],
        "confidence": 0.8,
    }
)
GET_EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "add",
                "endpoint_name": "/add",
                "method": "GET",
                "rationale": "Read-only computation.",
                "confidence": 0.85,
            }
        ]
    }
)
EMPTY_REVIEW_RESPONSE = json.dumps({"findings": [], "confidence": 0.9})
EMPTY_RISK_RESPONSE = json.dumps({"findings": []})
EMPTY_SECURITY_RESPONSE = json.dumps({"findings": []})
EMPTY_COMPATIBILITY_RESPONSE = json.dumps({"findings": [], "confidence": 0.9})
RISK_RESPONSE_WITH_SECRET = json.dumps(
    {
        "findings": [
            {
                "category": "DEPENDENCY",
                "severity": "WARNING",
                "evidence": "found a hardcoded token nearby: api_key=sk-abcdEFGH12345678ijkl in a related config",
                "confidence": 0.5,
            }
        ]
    }
)

HAPPY_SCRIPT = [
    make_response(ANALYSIS_RESPONSE),
    make_response(CANDIDATE_RESPONSE),
    make_response(INPUT_SCHEMA_RESPONSE),
    make_response(OUTPUT_SCHEMA_RESPONSE),
    make_response(INTENT_RESPONSE),
    make_response(GET_EXPOSURE_RESPONSE),
    make_response(EMPTY_REVIEW_RESPONSE),
    make_response(EMPTY_RISK_RESPONSE),
    make_response(EMPTY_SECURITY_RESPONSE),
    make_response(EMPTY_COMPATIBILITY_RESPONSE),
]


def _approved_decision(env):
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)

    env["orchestration"].analyze("nb-1")
    env["orchestration"].review("nb-1")
    return env["orchestration"].recommend("nb-1")


def test_successful_export_produces_a_valid_payload():
    env = build_env(list(HAPPY_SCRIPT))
    decision = _approved_decision(env)

    payload = env["export"].export(decision, "json")

    assert env["export"].validate_export(payload) is True
    parsed = json.loads(payload)
    assert parsed["approved"] is True
    assert parsed["notebook_id"] == "nb-1"
    assert parsed["decision_id"] == decision.decision_id
    assert len(parsed["recommendations"]) == 1
    assert parsed["recommendations"][0]["endpoint"] == "GET /add"


def test_rejected_decision_cannot_be_exported():
    env = build_env(list(HAPPY_SCRIPT))
    decision = _approved_decision(env)
    rejected = dataclasses.replace(decision, approved=False)

    with pytest.raises(DecisionNotApprovedError):
        env["export"].export(rejected, "json")


def test_schema_is_preserved_exactly():
    env = build_env(list(HAPPY_SCRIPT))
    decision = _approved_decision(env)
    candidate = env["api_candidate"].candidates("nb-1")[0]
    input_schema = env["input_schema"].get(candidate.candidate_id)
    output_schema = env["output_schema"].get(candidate.candidate_id)

    payload = json.loads(env["export"].export(decision, "json"))

    exported_schema = payload["recommendations"][0]["schema"]
    assert exported_schema["input"]["types"] == input_schema.types
    assert exported_schema["input"]["required"] == input_schema.required
    assert exported_schema["output"]["types"] == output_schema.types
    assert exported_schema["output"]["nullable"] == output_schema.nullable


def test_warnings_are_preserved_in_the_export():
    env = build_env(list(HAPPY_SCRIPT))
    decision = _approved_decision(env)
    assert decision.warnings  # no generated tests + no auth both surface as warnings

    payload = json.loads(env["export"].export(decision, "json"))

    assert len(payload["warnings"]) == len(decision.warnings)
    exported_categories = {w["category"] for w in payload["warnings"]}
    original_categories = {w["category"] for w in decision.warnings}
    assert exported_categories == original_categories


def test_export_is_deterministic_across_repeated_calls():
    env = build_env(list(HAPPY_SCRIPT))
    decision = _approved_decision(env)

    first = env["export"].export(decision, "json")
    second = env["export"].export(decision, "json")

    assert first == second


def test_secret_like_evidence_is_redacted_in_the_export():
    script = list(HAPPY_SCRIPT)
    script[7] = make_response(RISK_RESPONSE_WITH_SECRET)  # replaces the empty risk-analysis response
    env = build_env(script)
    decision = _approved_decision(env)

    payload = json.loads(env["export"].export(decision, "json"))
    serialized = json.dumps(payload)

    assert "sk-abcdEFGH12345678ijkl" not in serialized
    assert any(w["message"] == "[REDACTED]" for w in payload["warnings"])


def test_malformed_decision_and_unsupported_format_are_rejected():
    env = build_env(list(HAPPY_SCRIPT))
    decision = _approved_decision(env)

    with pytest.raises(UnsupportedFormatError):
        env["export"].export(decision, "yaml")

    broken = dataclasses.replace(decision, recommendations=["never-tracked-id"])
    with pytest.raises(MalformedDecisionError):
        env["export"].export(broken, "json")

    with pytest.raises(MalformedExportError):
        env["export"].validate_export("not json")
