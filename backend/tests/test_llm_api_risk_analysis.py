import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureService
from backend.api_risk_analysis import (
    CRITICAL,
    DEPENDENCY,
    INPUT,
    RELIABILITY,
    SECURITY,
    LLMAPIRiskService,
    MalformedRiskResponseError,
)
from backend.api_schema_review import LLMAPISchemaReviewService
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

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "test_generation": test_generation_service,
        "dependency": dependency_service,
        "exposure": exposure_service,
        "review": schema_review_service,
        "api_tests": api_test_service,
        "risk": risk_service,
    }


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def helper():\n    return 1"},
        {"cell_type": "code", "source": "def add(a, b):\n    return {'sum': a + b + helper()}"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {
        "imports": [],
        "functions": [{"name": "helper", "cell_index": 1}, {"name": "add", "cell_index": 2}],
        "dependencies": [],
    }
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
DEPENDENCY_RESPONSE = json.dumps(
    {
        "edges": [
            {"source": "function:helper", "target": "function:add", "dependency_type": "FUNCTION", "confidence": 0.9}
        ]
    }
)
EMPTY_RISK_RESPONSE = json.dumps({"findings": []})
LLM_RISK_FINDING_RESPONSE = json.dumps(
    {
        "findings": [
            {
                "category": "RELIABILITY",
                "severity": "WARNING",
                "evidence": "helper() has no error handling if called before initialization.",
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


def test_risk_detection_surfaces_grounded_findings_across_categories():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(DEPENDENCY_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(LLM_RISK_FINDING_RESPONSE),
        ]
    )
    analysis, _candidate = _register_candidate(env)
    env["dependency"].analyze(analysis.analysis_id)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    # Deliberately never schema-reviewed, and no tests generated -- both become findings.

    findings = env["risk"].analyze(recommendation)

    categories = {f.category for f in findings}
    assert INPUT in categories  # never schema-reviewed
    assert DEPENDENCY in categories  # add depends on helper
    assert RELIABILITY in categories  # no generated test cases
    assert any(f.evidence.startswith("helper()") for f in findings)
    assert all(f.evidence.strip() for f in findings)
    assert env["risk"].findings("POST /add") == findings


@pytest.mark.parametrize(
    "bad_response",
    [
        json.dumps({"findings": [{"category": "UNKNOWN", "severity": "WARNING", "evidence": "x", "confidence": 0.5}]}),
        json.dumps({"findings": [{"category": "INPUT", "severity": "CATASTROPHIC", "evidence": "x", "confidence": 0.5}]}),
        json.dumps({"findings": [{"category": "INPUT", "severity": "WARNING", "evidence": "x", "confidence": 1.5}]}),
    ],
)
def test_severity_and_category_are_validated(bad_response):
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(bad_response),
        ]
    )
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)

    with pytest.raises(MalformedRiskResponseError):
        env["risk"].analyze(recommendation)


def test_finding_without_evidence_is_rejected():
    empty_evidence_response = json.dumps(
        {"findings": [{"category": "INPUT", "severity": "WARNING", "evidence": "   ", "confidence": 0.5}]}
    )
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(empty_evidence_response),
        ]
    )
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)

    with pytest.raises(MalformedRiskResponseError):
        env["risk"].analyze(recommendation)


DANGEROUS_NOTEBOOK = {
    "notebook_id": "nb-2",
    "cells": [{"cell_type": "code", "source": "def run(cmd, b):\n    exec(cmd)\n    return {'sum': b}"}],
}
DANGEROUS_ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "run", "cell_index": 0}], "dependencies": []}
)
DANGEROUS_CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "run",
                "inputs": ["cmd", "b"],
                "outputs": ["sum"],
                "confidence": 0.9,
                "rationale": "Runs a command.",
            }
        ]
    }
)
DANGEROUS_INPUT_SCHEMA_RESPONSE = json.dumps(
    {
        "fields": [
            {"name": "cmd", "type": "str", "constraints": {}, "ambiguous": False},
            {"name": "b", "type": "int", "constraints": {}, "ambiguous": False},
        ]
    }
)
DANGEROUS_OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "sum", "type": "int", "nullable": False, "structure": {}, "contradictory": False}]}
)
DANGEROUS_EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "run",
                "endpoint_name": "/run",
                "method": "POST",
                "rationale": "Runs a command.",
                "confidence": 0.5,
            }
        ]
    }
)


def test_critical_filtering_distinguishes_severities():
    env = build_env(
        [
            make_response(DANGEROUS_ANALYSIS_RESPONSE),
            make_response(DANGEROUS_CANDIDATE_RESPONSE),
            make_response(DANGEROUS_INPUT_SCHEMA_RESPONSE),
            make_response(DANGEROUS_OUTPUT_SCHEMA_RESPONSE),
            make_response(DANGEROUS_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(EMPTY_RISK_RESPONSE),
        ]
    )
    dangerous_analysis = env["notebook_analysis"].analyze(DANGEROUS_NOTEBOOK)
    [dangerous_candidate] = env["api_candidate"].analyze(dangerous_analysis.analysis_id)
    env["input_schema"].infer(dangerous_candidate.candidate_id)
    env["output_schema"].infer(dangerous_candidate.candidate_id)
    dangerous_intent = LLMNotebookAPIIntent(
        notebook_id="nb-2",
        operations=[{"operation": "expose run", "function": "run", "ambiguous": False}],
        candidate_functions=["run"],
        requested_exposure="PUBLIC",
        constraints=[],
        confidence=0.5,
    )
    [dangerous_recommendation] = env["exposure"].recommend(dangerous_intent)
    env["review"].review(dangerous_recommendation)

    env["risk"].analyze(dangerous_recommendation)

    assert env["risk"].blocking("POST /run") is True
    security_findings = [f for f in env["risk"].findings("POST /run") if f.category == SECURITY]
    assert any(f.severity == CRITICAL for f in security_findings)


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
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)

    with pytest.raises(MalformedRiskResponseError):
        env["risk"].analyze(recommendation)


SUB_EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "helper",
                "endpoint_name": "/helper",
                "method": "GET",
                "rationale": "Exposes helper directly.",
                "confidence": 0.5,
            }
        ]
    }
)


def test_endpoint_isolation_keeps_findings_scoped():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(EMPTY_RISK_RESPONSE),
        ]
    )
    _register_candidate(env)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)

    env["risk"].analyze(recommendation)

    assert env["risk"].findings("POST /add")
    assert env["risk"].findings("GET /helper") == []
    assert env["risk"].blocking("GET /helper") is False
