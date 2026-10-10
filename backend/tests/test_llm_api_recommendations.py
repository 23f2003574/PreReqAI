import copy
import json

import pytest

from backend.api_candidates import LLMAPICandidateService
from backend.api_recommendations import (
    LLMAPIRecommendationService,
    MalformedRecommendationError,
    UnsupportedEvidenceError,
)
from backend.code_quality import LLMCodeQualityService
from backend.input_schema import LLMInputSchemaService
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_dependencies import LLMNotebookDependencyService
from backend.output_schema import LLMOutputSchemaService


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
    candidate_service = LLMAPICandidateService(
        notebook_analysis_service,
        orchestration_service=orchestration_service,
        context_service=context_service,
    )
    input_schema_service = LLMInputSchemaService(
        candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    output_schema_service = LLMOutputSchemaService(
        candidate_service, notebook_analysis_service, orchestration_service, context_service
    )
    dependency_service = LLMNotebookDependencyService(
        notebook_analysis_service, orchestration_service, context_service
    )
    quality_service = LLMCodeQualityService(notebook_analysis_service, orchestration_service, context_service)
    recommendation_service = LLMAPIRecommendationService(
        candidate_service,
        notebook_analysis_service,
        input_schema_service,
        output_schema_service,
        quality_service,
        orchestration_service,
        context_service,
        dependency_service=dependency_service,
    )

    return {
        "notebook_analysis": notebook_analysis_service,
        "candidate": candidate_service,
        "input_schema": input_schema_service,
        "output_schema": output_schema_service,
        "dependency": dependency_service,
        "quality": quality_service,
        "recommendation": recommendation_service,
    }


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [{"cell_type": "code", "source": "def divide(a: int, b: int) -> float:\n    return a / b"}],
}
FUNCTIONS = [{"name": "divide", "cell_index": 0}]
ANALYSIS_RESPONSE = json.dumps({"imports": [], "functions": FUNCTIONS, "dependencies": []})
CANDIDATE_RESPONSE = json.dumps(
    {
        "candidates": [
            {
                "function_name": "divide",
                "inputs": ["a", "b"],
                "outputs": ["result"],
                "confidence": 0.9,
                "rationale": "Simple numeric function.",
            }
        ]
    }
)


def input_field_entry(name, field_type="float"):
    return {"name": name, "type": field_type, "constraints": {}, "ambiguous": False}


INPUT_SCHEMA_RESPONSE = json.dumps({"fields": [input_field_entry("a"), input_field_entry("b")]})


def output_field_entry(name, field_type="str"):
    return {"name": name, "type": field_type, "nullable": False, "structure": {}, "contradictory": False}


OUTPUT_SCHEMA_RESPONSE = json.dumps({"fields": [output_field_entry("result")]})

DEPENDENCY_RESPONSE = json.dumps(
    {
        "edges": [
            {"source": "cell:0", "target": "function:divide", "dependency_type": "FUNCTION", "confidence": 0.9}
        ]
    }
)

QUALITY_RESPONSE = json.dumps(
    {
        "findings": [
            {
                "cell_id": "cell:0",
                "category": "RISK",
                "severity": "ERROR",
                "message": "possible ZeroDivisionError when b is 0",
                "confidence": 0.9,
            }
        ]
    }
)


def recommendation_entry(category, evidence_refs, severity="WARNING", confidence=0.8):
    return {
        "category": category,
        "change": "Validate b is non-zero before dividing.",
        "rationale": "The quality finding flags a division-by-zero risk in this cell.",
        "confidence": confidence,
        "severity": severity,
        "evidence_refs": evidence_refs,
    }


def build_pipeline(recommendation_response):
    services = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(CANDIDATE_RESPONSE),
            make_response(INPUT_SCHEMA_RESPONSE),
            make_response(OUTPUT_SCHEMA_RESPONSE),
            make_response(DEPENDENCY_RESPONSE),
            make_response(QUALITY_RESPONSE),
            make_response(recommendation_response),
        ]
    )
    analysis = services["notebook_analysis"].analyze(NOTEBOOK)
    candidates = services["candidate"].analyze(analysis.analysis_id)
    candidate_id = candidates[0].candidate_id
    services["input_schema"].infer(candidate_id)
    services["output_schema"].infer(candidate_id)
    services["dependency"].analyze(analysis.analysis_id)
    services["quality"].analyze(analysis.analysis_id)
    return services, candidate_id


def valid_recommendation_response():
    return json.dumps(
        {
            "recommendations": [
                recommendation_entry(
                    "RELIABILITY",
                    ["quality:finding-nb-1-1", "cell:0"],
                    severity="ERROR",
                    confidence=0.9,
                ),
                recommendation_entry(
                    "SCHEMA",
                    ["schema:input", "schema:output"],
                    severity="INFO",
                    confidence=0.6,
                ),
            ]
        }
    )


def test_recommendation_generation():
    services, candidate_id = build_pipeline(valid_recommendation_response())

    generated = services["recommendation"].analyze(candidate_id)

    assert len(generated) == 2
    assert services["recommendation"].recommendations(candidate_id) == generated


def test_category_validation():
    bad_response = json.dumps(
        {"recommendations": [recommendation_entry("SECURITY", ["cell:0"])]}
    )
    services, candidate_id = build_pipeline(bad_response)

    with pytest.raises(MalformedRecommendationError):
        services["recommendation"].analyze(candidate_id)


def test_confidence_validation():
    services, candidate_id = build_pipeline(
        json.dumps({"recommendations": [recommendation_entry("SCHEMA", ["cell:0"], confidence=1.5)]})
    )
    with pytest.raises(MalformedRecommendationError):
        services["recommendation"].analyze(candidate_id)


def test_evidence_backed_rationale_rejects_unknown_evidence():
    services, candidate_id = build_pipeline(
        json.dumps({"recommendations": [recommendation_entry("RELIABILITY", ["quality:does-not-exist"])]})
    )
    with pytest.raises(UnsupportedEvidenceError):
        services["recommendation"].analyze(candidate_id)


def test_evidence_backed_rationale_requires_at_least_one_ref():
    services, candidate_id = build_pipeline(
        json.dumps({"recommendations": [recommendation_entry("RELIABILITY", [])]})
    )
    with pytest.raises(MalformedRecommendationError):
        services["recommendation"].analyze(candidate_id)


def test_critical_filtering():
    services, candidate_id = build_pipeline(valid_recommendation_response())

    generated = services["recommendation"].analyze(candidate_id)
    critical = services["recommendation"].critical(candidate_id)

    assert len(critical) == 1
    assert critical[0].severity == "ERROR"
    assert critical[0] in generated


def test_source_and_api_immutability():
    services, candidate_id = build_pipeline(valid_recommendation_response())

    analysis_before = copy.deepcopy(services["notebook_analysis"].get_by_notebook("nb-1"))
    candidate_before = copy.deepcopy(services["candidate"].get(candidate_id))
    input_schema_before = copy.deepcopy(services["input_schema"].get(candidate_id))
    output_schema_before = copy.deepcopy(services["output_schema"].get(candidate_id))

    services["recommendation"].analyze(candidate_id)

    assert services["notebook_analysis"].get_by_notebook("nb-1") == analysis_before
    assert services["candidate"].get(candidate_id) == candidate_before
    assert services["input_schema"].get(candidate_id) == input_schema_before
    assert services["output_schema"].get(candidate_id) == output_schema_before
