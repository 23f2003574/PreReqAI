import json

import pytest

from backend.api_candidates import (
    LLMAPICandidateService,
    MalformedCandidateResponseError,
    UnknownFunctionCandidateError,
)
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_dependencies import LLMNotebookDependencyService


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
    dependency_service = LLMNotebookDependencyService(
        notebook_analysis_service, orchestration_service, context_service
    )
    candidate_service = LLMAPICandidateService(
        notebook_analysis_service, dependency_service, orchestration_service, context_service
    )

    return notebook_analysis_service, dependency_service, candidate_service


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "import numpy as np\nimport pandas as pd"},
        {"cell_type": "markdown", "source": "## Helper"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {
        "imports": ["import numpy as np", "import pandas as pd"],
        "functions": [{"name": "add", "cell_index": 3}],
        "dependencies": ["numpy", "pandas"],
    }
)
DEPENDENCY_RESPONSE = json.dumps(
    {
        "edges": [
            {"source": "cell:1", "target": "import:0", "dependency_type": "IMPORT", "confidence": 0.95},
            {"source": "cell:3", "target": "function:add", "dependency_type": "FUNCTION", "confidence": 0.99},
        ]
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
                "rationale": "Pure function with simple numeric inputs and a single numeric output.",
            }
        ]
    }
)


def run_pipeline(candidate_response, dependency_response=DEPENDENCY_RESPONSE):
    notebook_analysis_service, dependency_service, candidate_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(dependency_response), make_response(candidate_response)]
    )
    analysis = notebook_analysis_service.analyze(NOTEBOOK)
    dependency_service.analyze(analysis.analysis_id)
    candidates = candidate_service.analyze(analysis.analysis_id)
    return notebook_analysis_service, candidate_service, analysis, candidates


def test_candidate_detection():
    _, candidate_service, analysis, candidates = run_pipeline(CANDIDATE_RESPONSE)

    assert len(candidates) == 1
    assert candidates[0].function_name == "add"
    assert candidates[0].notebook_id == analysis.notebook_id
    assert candidate_service.candidates("nb-1") == candidates


def test_input_output_extraction():
    _, candidate_service, _, candidates = run_pipeline(CANDIDATE_RESPONSE)

    candidate_id = candidates[0].candidate_id
    assert candidate_service.inputs(candidate_id) == ["a", "b"]
    assert candidate_service.outputs(candidate_id) == ["sum"]


@pytest.mark.parametrize("bad_confidence", [-0.1, 1.1, "high"])
def test_confidence_validation(bad_confidence):
    response = json.dumps(
        {
            "candidates": [
                {
                    "function_name": "add",
                    "inputs": ["a", "b"],
                    "outputs": ["sum"],
                    "confidence": bad_confidence,
                    "rationale": "Pure function, good API candidate.",
                }
            ]
        }
    )

    with pytest.raises(MalformedCandidateResponseError):
        run_pipeline(response)


def test_confidence_required():
    response = json.dumps(
        {
            "candidates": [
                {"function_name": "add", "inputs": ["a", "b"], "outputs": ["sum"], "rationale": "Good candidate."}
            ]
        }
    )

    with pytest.raises(MalformedCandidateResponseError):
        run_pipeline(response)


def test_unknown_function_rejection():
    response = json.dumps(
        {
            "candidates": [
                {
                    "function_name": "does_not_exist",
                    "inputs": ["a"],
                    "outputs": ["b"],
                    "confidence": 0.8,
                    "rationale": "Looks useful.",
                }
            ]
        }
    )

    with pytest.raises(UnknownFunctionCandidateError):
        run_pipeline(response)


def test_multiple_candidates():
    notebook = {
        "notebook_id": "nb-2",
        "cells": [
            {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
            {"cell_type": "code", "source": "def multiply(a, b):\n    return a * b"},
        ],
    }
    analysis_response = json.dumps(
        {
            "imports": [],
            "functions": [{"name": "add", "cell_index": 0}, {"name": "multiply", "cell_index": 1}],
            "dependencies": [],
        }
    )
    candidate_response = json.dumps(
        {
            "candidates": [
                {
                    "function_name": "add",
                    "inputs": ["a", "b"],
                    "outputs": ["sum"],
                    "confidence": 0.9,
                    "rationale": "Simple pure function.",
                },
                {
                    "function_name": "multiply",
                    "inputs": ["a", "b"],
                    "outputs": ["product"],
                    "confidence": 0.85,
                    "rationale": "Simple pure function.",
                },
            ]
        }
    )

    notebook_analysis_service, dependency_service, candidate_service = build_env(
        [make_response(analysis_response), make_response(candidate_response)]
    )
    analysis = notebook_analysis_service.analyze(notebook)
    candidates = candidate_service.analyze(analysis.analysis_id)

    assert len(candidates) == 2
    assert {c.function_name for c in candidates} == {"add", "multiply"}
    assert candidate_service.candidates("nb-2") == candidates


def test_source_preservation():
    notebook_analysis_service, _, analysis, candidates = run_pipeline(CANDIDATE_RESPONSE)

    original_source = NOTEBOOK["cells"][3]["source"]
    stored_analysis = notebook_analysis_service.get(analysis.analysis_id)

    assert stored_analysis.cells[3].source == original_source
    assert candidates[0].function_name == stored_analysis.functions[0]["name"]


def test_malformed_candidate_response_is_rejected():
    with pytest.raises(MalformedCandidateResponseError):
        run_pipeline("here are the candidates: add()")

    with pytest.raises(MalformedCandidateResponseError):
        run_pipeline(json.dumps({"candidates": [{"function_name": "add"}]}))
