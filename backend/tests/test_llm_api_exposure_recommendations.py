import json

import pytest

from backend.api_exposure_recommendations import (
    LLMAPIExposureService,
    MalformedRecommendationResponseError,
    UnknownExposureFunctionError,
    UnknownRecommendationError,
    UnsupportedMethodError,
)
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_api_intent import LLMNotebookAPIIntent


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
    exposure_service = LLMAPIExposureService(notebook_analysis_service, orchestration_service, context_service)

    return notebook_analysis_service, exposure_service


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
        {"cell_type": "code", "source": "def sub(a, b):\n    return a - b"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {
        "imports": [],
        "functions": [{"name": "add", "cell_index": 1}, {"name": "sub", "cell_index": 2}],
        "dependencies": [],
    }
)

SMALLER_NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def sub(a, b):\n    return a - b"},
    ],
}
SMALLER_ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "sub", "cell_index": 1}], "dependencies": []}
)


def _confident_intent(functions):
    return LLMNotebookAPIIntent(
        notebook_id="nb-1",
        operations=[
            {"operation": f"expose {name}", "function": name, "ambiguous": False} for name in functions
        ],
        candidate_functions=list(functions),
        requested_exposure="PUBLIC",
        constraints=[],
        confidence=0.8,
    )


def _mixed_intent():
    return LLMNotebookAPIIntent(
        notebook_id="nb-1",
        operations=[
            {"operation": "expose add", "function": "add", "ambiguous": False},
            {"operation": "expose something unclear", "function": None, "ambiguous": True},
        ],
        candidate_functions=["add"],
        requested_exposure="PUBLIC",
        constraints=[],
        confidence=0.6,
    )


def _fully_ambiguous_intent():
    return LLMNotebookAPIIntent(
        notebook_id="nb-1",
        operations=[{"operation": "expose something unclear", "function": None, "ambiguous": True}],
        candidate_functions=[],
        requested_exposure="UNSPECIFIED",
        constraints=[],
        confidence=0.2,
    )


ADD_RECOMMENDATION_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "add",
                "endpoint_name": "/add",
                "method": "POST",
                "rationale": "Pure arithmetic function, best exposed as a POST.",
                "confidence": 0.85,
            }
        ]
    }
)
TWO_FUNCTION_RECOMMENDATION_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "add",
                "endpoint_name": "/add",
                "method": "POST",
                "rationale": "Pure arithmetic function.",
                "confidence": 0.85,
            },
            {
                "function_name": "sub",
                "endpoint_name": "/sub",
                "method": "POST",
                "rationale": "Pure arithmetic function.",
                "confidence": 0.8,
            },
        ]
    }
)
UNKNOWN_FUNCTION_RECOMMENDATION_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "multiply",
                "endpoint_name": "/multiply",
                "method": "POST",
                "rationale": "Not actually part of the intent.",
                "confidence": 0.5,
            }
        ]
    }
)
UNSUPPORTED_METHOD_RESPONSE = json.dumps(
    {
        "recommendations": [
            {
                "function_name": "add",
                "endpoint_name": "/add",
                "method": "TRACE",
                "rationale": "Unsupported by the compiler.",
                "confidence": 0.5,
            }
        ]
    }
)


def test_valid_recommendation_is_grounded_in_the_confident_intent():
    notebook_analysis, exposure_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_RECOMMENDATION_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)

    recommendations = exposure_service.recommend(_confident_intent(["add"]))

    assert len(recommendations) == 1
    rec = recommendations[0]
    assert rec.function_name == "add"
    assert rec.endpoint_name == "/add"
    assert rec.method == "POST"
    assert rec.rationale
    assert 0.0 <= rec.confidence <= 1.0
    assert exposure_service.recommendations("nb-1") == recommendations


def test_recommendation_for_unmapped_function_is_rejected():
    notebook_analysis, exposure_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(UNKNOWN_FUNCTION_RECOMMENDATION_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)

    with pytest.raises(UnknownExposureFunctionError):
        exposure_service.recommend(_confident_intent(["add"]))


def test_unsupported_http_method_is_rejected():
    notebook_analysis, exposure_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(UNSUPPORTED_METHOD_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)

    with pytest.raises(UnsupportedMethodError):
        exposure_service.recommend(_confident_intent(["add"]))


def test_ambiguous_operations_are_skipped_not_guessed():
    notebook_analysis, exposure_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_RECOMMENDATION_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)

    recommendations = exposure_service.recommend(_mixed_intent())

    assert {r.function_name for r in recommendations} == {"add"}


def test_fully_ambiguous_intent_produces_no_recommendations_without_calling_the_llm():
    notebook_analysis, exposure_service = build_env([make_response(ANALYSIS_RESPONSE)])
    notebook_analysis.analyze(NOTEBOOK)

    recommendations = exposure_service.recommend(_fully_ambiguous_intent())

    assert recommendations == []


def test_multiple_candidates_all_get_recommendations():
    notebook_analysis, exposure_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(TWO_FUNCTION_RECOMMENDATION_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)

    recommendations = exposure_service.recommend(_confident_intent(["add", "sub"]))

    assert {r.function_name for r in recommendations} == {"add", "sub"}


def test_validate_detects_a_function_removed_since_the_recommendation():
    notebook_analysis, exposure_service = build_env(
        [
            make_response(ANALYSIS_RESPONSE),
            make_response(ADD_RECOMMENDATION_RESPONSE),
            make_response(SMALLER_ANALYSIS_RESPONSE),
        ]
    )
    notebook_analysis.analyze(NOTEBOOK)
    [recommendation] = exposure_service.recommend(_confident_intent(["add"]))

    assert exposure_service.validate(recommendation) is True

    notebook_analysis.analyze(SMALLER_NOTEBOOK)

    with pytest.raises(UnknownExposureFunctionError):
        exposure_service.validate(recommendation)


def test_validate_rejects_a_recommendation_this_service_never_produced():
    _notebook_analysis, exposure_service = build_env([])
    from backend.api_exposure_recommendations import LLMAPIExposureRecommendation

    foreign = LLMAPIExposureRecommendation(
        recommendation_id="not-mine",
        function_name="add",
        endpoint_name="/add",
        method="POST",
        rationale="n/a",
        confidence=0.5,
    )

    with pytest.raises(UnknownRecommendationError):
        exposure_service.validate(foreign)


def test_recommend_never_mutates_notebook_source():
    notebook_analysis, exposure_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(ADD_RECOMMENDATION_RESPONSE)]
    )
    analysis = notebook_analysis.analyze(NOTEBOOK)
    original_sources = [cell.source for cell in analysis.cells]

    exposure_service.recommend(_confident_intent(["add"]))

    current = notebook_analysis.get_by_notebook("nb-1")
    assert [cell.source for cell in current.cells] == original_sources
    assert current is analysis
