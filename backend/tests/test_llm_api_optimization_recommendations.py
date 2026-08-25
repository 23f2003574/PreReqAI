import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureService
from backend.api_optimization_recommendations import (
    HIGH,
    LLMAPIOptimizationService,
    MalformedOptimizationResponseError,
    RiskConflictError,
    SchemaNotApprovedError,
    UnknownOptimizationError,
)
from backend.api_risk_analysis import LLMAPIRiskService
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
    optimization_service = LLMAPIOptimizationService(
        exposure_service,
        schema_review_service,
        risk_service,
        api_candidate_service,
        notebook_analysis_service,
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
        "exposure": exposure_service,
        "review": schema_review_service,
        "risk": risk_service,
        "optimization": optimization_service,
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
EMPTY_RISK_RESPONSE = json.dumps({"findings": []})

TWO_OPTIMIZATION_RESPONSE = json.dumps(
    {
        "optimizations": [
            {
                "category": "CODE",
                "recommendation": "Avoid rebuilding the result dict key on every call.",
                "rationale": "Marginal reduction in per-call dict allocation overhead.",
                "expected_impact": "LOW",
                "confidence": 0.6,
            },
            {
                "category": "COMPUTE",
                "recommendation": "Hoist the computation out of any enclosing hot loop at call sites.",
                "rationale": "Profiling similar call patterns showed a 3x reduction in wall-clock time.",
                "expected_impact": "HIGH",
                "confidence": 0.75,
            },
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


def _approved_recommendation(env):
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    env["review"].review(recommendation)
    return recommendation


def test_analyze_generates_evidence_backed_optimizations():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(TWO_OPTIMIZATION_RESPONSE),
        ]
    )
    recommendation = _approved_recommendation(env)

    optimizations = env["optimization"].analyze(recommendation)

    assert len(optimizations) == 2
    for optimization in optimizations:
        assert optimization.endpoint == "POST /add"
        assert optimization.recommendation.strip()
        assert optimization.rationale.strip()
    assert {o.category for o in optimizations} == {"CODE", "COMPUTE"}


@pytest.mark.parametrize(
    "bad_response",
    [
        json.dumps(
            {
                "optimizations": [
                    {
                        "category": "UNKNOWN",
                        "recommendation": "Do something.",
                        "rationale": "Some evidence.",
                        "expected_impact": "LOW",
                        "confidence": 0.5,
                    }
                ]
            }
        ),
        json.dumps(
            {
                "optimizations": [
                    {
                        "category": "CODE",
                        "recommendation": "Do something.",
                        "rationale": "Some evidence.",
                        "expected_impact": "EXTREME",
                        "confidence": 0.5,
                    }
                ]
            }
        ),
        json.dumps(
            {
                "optimizations": [
                    {
                        "category": "CODE",
                        "recommendation": "Do something.",
                        "rationale": "   ",
                        "expected_impact": "LOW",
                        "confidence": 0.5,
                    }
                ]
            }
        ),
        json.dumps(
            {
                "optimizations": [
                    {
                        "category": "CODE",
                        "recommendation": "Do something.",
                        "rationale": "Some evidence.",
                        "expected_impact": "LOW",
                        "confidence": 1.5,
                    }
                ]
            }
        ),
    ],
)
def test_category_and_confidence_and_impact_are_validated(bad_response):
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
    recommendation = _approved_recommendation(env)

    with pytest.raises(MalformedOptimizationResponseError):
        env["optimization"].analyze(recommendation)


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


def _dangerous_recommendation(env):
    analysis = env["notebook_analysis"].analyze(DANGEROUS_NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    intent = LLMNotebookAPIIntent(
        notebook_id="nb-2",
        operations=[{"operation": "expose run", "function": "run", "ambiguous": False}],
        candidate_functions=["run"],
        requested_exposure="PUBLIC",
        constraints=[],
        confidence=0.5,
    )
    [recommendation] = env["exposure"].recommend(intent)
    env["review"].review(recommendation)
    return recommendation


def test_blocking_risk_finding_prevents_optimization_analysis():
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
    recommendation = _dangerous_recommendation(env)
    env["risk"].analyze(recommendation)
    assert env["risk"].blocking("POST /run") is True

    with pytest.raises(RiskConflictError):
        env["optimization"].analyze(recommendation)


def test_high_impact_filters_to_only_high_expected_impact():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(TWO_OPTIMIZATION_RESPONSE),
        ]
    )
    recommendation = _approved_recommendation(env)
    env["optimization"].analyze(recommendation)

    high_impact = env["optimization"].high_impact("POST /add")

    assert len(high_impact) == 1
    assert high_impact[0].expected_impact == HIGH
    assert high_impact[0].category == "COMPUTE"


def test_unapproved_schema_review_is_rejected():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
        ]
    )
    analysis = env["notebook_analysis"].analyze(NOTEBOOK)
    [candidate] = env["api_candidate"].analyze(analysis.analysis_id)
    env["input_schema"].infer(candidate.candidate_id)
    env["output_schema"].infer(candidate.candidate_id)
    [recommendation] = env["exposure"].recommend(_confident_intent())
    # Deliberately never schema-reviewed.

    with pytest.raises(SchemaNotApprovedError):
        env["optimization"].analyze(recommendation)


def test_analysis_never_mutates_notebook_source():
    env = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(EXPOSURE_RESPONSE),
            make_response(EMPTY_REVIEW_RESPONSE),
            make_response(TWO_OPTIMIZATION_RESPONSE),
        ]
    )
    recommendation = _approved_recommendation(env)

    live_before = env["notebook_analysis"].get_by_notebook("nb-1").cells[1].source
    env["optimization"].analyze(recommendation)
    live_after = env["notebook_analysis"].get_by_notebook("nb-1").cells[1].source

    assert live_before == live_after == "def add(a, b):\n    return {'sum': a + b}"


def test_validate_rejects_unknown_optimization_id():
    env = build_env([])

    with pytest.raises(UnknownOptimizationError):
        env["optimization"].validate("never-generated")
