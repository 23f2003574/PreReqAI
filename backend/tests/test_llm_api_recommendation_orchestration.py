import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_compatibility_review import LLMAPICompatibilityService
from backend.api_exposure_recommendations import LLMAPIExposureService
from backend.api_recommendation_orchestration import (
    LLMAPIRecommendationOrchestrationService,
    MissingAnalysisError,
)
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
from backend.notebook_api_intent import LLMNotebookAPIIntentService, MalformedIntentResponseError
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

    return {
        "notebook_analysis": notebook_analysis_service,
        "api_candidate": api_candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "exposure": exposure_service,
        "review": schema_review_service,
        "orchestration": orchestration,
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


def _register_candidate(env, notebook=NOTEBOOK):
    analysis = env["notebook_analysis"].analyze(notebook)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    return analysis, candidate


def test_successful_recommendation_produces_an_approved_decision():
    env = build_env(list(HAPPY_SCRIPT))
    _register_candidate(env)

    env["orchestration"].analyze("nb-1")
    recommendations = env["orchestration"].review("nb-1")
    decision = env["orchestration"].recommend("nb-1")

    assert decision.notebook_id == "nb-1"
    assert decision.recommendations == [r.recommendation_id for r in recommendations]
    assert decision.approved is True
    assert decision.blocking_findings == []
    assert env["orchestration"].decision("nb-1") == decision


def test_review_and_recommend_require_the_prior_stage():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(INTENT_RESPONSE),
        ]
    )
    _register_candidate(env)

    with pytest.raises(MissingAnalysisError):
        env["orchestration"].review("nb-1")

    env["orchestration"].analyze("nb-1")

    with pytest.raises(MissingAnalysisError):
        env["orchestration"].recommend("nb-1")


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
DANGEROUS_INTENT_RESPONSE = json.dumps(
    {
        "operations": [{"operation": "expose run", "function": "run", "ambiguous": False}],
        "candidate_functions": ["run"],
        "requested_exposure": "PUBLIC",
        "constraints": [],
        "confidence": 0.5,
    }
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


def test_blocking_risk_and_security_findings_reject_the_decision():
    env = build_env(
        [
            make_response(DANGEROUS_ANALYSIS_RESPONSE),
            make_response(DANGEROUS_CANDIDATE_RESPONSE),
            make_response(DANGEROUS_INPUT_SCHEMA_RESPONSE),
            make_response(DANGEROUS_OUTPUT_SCHEMA_RESPONSE),
            make_response(DANGEROUS_INTENT_RESPONSE),
            make_response(DANGEROUS_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(EMPTY_RISK_RESPONSE),
            make_response(EMPTY_SECURITY_RESPONSE),
            make_response(EMPTY_COMPATIBILITY_RESPONSE),
        ]
    )
    _register_candidate(env, DANGEROUS_NOTEBOOK)

    env["orchestration"].analyze("nb-2")
    env["orchestration"].review("nb-2")
    decision = env["orchestration"].recommend("nb-2")

    assert decision.approved is False
    sources = {f["source"] for f in decision.blocking_findings}
    assert "RISK" in sources
    assert "SECURITY" in sources


DATA_NOTEBOOK = {
    "notebook_id": "nb-3",
    "cells": [{"cell_type": "code", "source": "def get_data(source) -> dict:\n    return fetch(source)"}],
}
DATA_ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "get_data", "cell_index": 0}], "dependencies": []}
)
DATA_CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "get_data",
                "inputs": ["source"],
                "outputs": ["data"],
                "confidence": 0.9,
                "rationale": "Fetches structured data.",
            }
        ]
    }
)
DATA_INPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "source", "type": "str", "constraints": {}, "ambiguous": False}]}
)
DATA_OUTPUT_SCHEMA_RESPONSE = json.dumps(
    {"fields": [{"name": "data", "type": "dict", "nullable": False, "structure": {}, "contradictory": False}]}
)
DATA_INTENT_RESPONSE = json.dumps(
    {
        "operations": [{"operation": "expose get_data", "function": "get_data", "ambiguous": False}],
        "candidate_functions": ["get_data"],
        "requested_exposure": "PUBLIC",
        "constraints": [],
        "confidence": 0.6,
    }
)
DATA_EXPOSURE_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "get_data",
                "endpoint_name": "/data",
                "method": "GET",
                "rationale": "Read-only fetch.",
                "confidence": 0.7,
            }
        ]
    }
)


def test_compatibility_failure_rejects_the_decision():
    env = build_env(
        [
            make_response(DATA_ANALYSIS_RESPONSE),
            make_response(DATA_CANDIDATE_RESPONSE),
            make_response(DATA_INPUT_SCHEMA_RESPONSE),
            make_response(DATA_OUTPUT_SCHEMA_RESPONSE),
            make_response(DATA_INTENT_RESPONSE),
            make_response(DATA_EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(EMPTY_RISK_RESPONSE),
            make_response(EMPTY_SECURITY_RESPONSE),
            make_response(EMPTY_COMPATIBILITY_RESPONSE),
        ]
    )
    _register_candidate(env, DATA_NOTEBOOK)

    env["orchestration"].analyze("nb-3")
    env["orchestration"].review("nb-3")
    decision = env["orchestration"].recommend("nb-3")

    assert decision.approved is False
    compatibility_findings = [f for f in decision.blocking_findings if f["source"] == "COMPATIBILITY"]
    assert compatibility_findings
    assert any(f["category"] == "SCHEMA_INCOMPATIBILITY" for f in compatibility_findings)


def test_warning_only_result_is_still_approved():
    env = build_env(list(HAPPY_SCRIPT))
    _register_candidate(env)

    env["orchestration"].analyze("nb-1")
    env["orchestration"].review("nb-1")
    decision = env["orchestration"].recommend("nb-1")

    assert decision.approved is True
    assert decision.blocking_findings == []
    assert decision.warnings  # no generated tests + no auth both surface as warnings


def test_malformed_llm_response_propagates_from_an_early_stage():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response("not json"),
        ]
    )
    _register_candidate(env)

    with pytest.raises(MalformedIntentResponseError):
        env["orchestration"].analyze("nb-1")


def test_decision_is_deterministic_across_repeated_reads():
    env = build_env(list(HAPPY_SCRIPT))
    _register_candidate(env)

    env["orchestration"].analyze("nb-1")
    env["orchestration"].review("nb-1")
    env["orchestration"].recommend("nb-1")

    first = env["orchestration"].decision("nb-1")
    second = env["orchestration"].decision("nb-1")

    assert first == second
    assert first is second
