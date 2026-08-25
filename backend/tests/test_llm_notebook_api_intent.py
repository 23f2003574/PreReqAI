import json

import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService, UnknownAnalysisError
from backend.notebook_api_intent import (
    LLMNotebookAPIIntentService,
    MalformedIntentResponseError,
    UnknownIntentFunctionError,
)
from backend.notebook_summary import LLMNotebookSummaryService


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
    summary_service = LLMNotebookSummaryService(notebook_analysis_service, orchestration_service, context_service)
    intent_service = LLMNotebookAPIIntentService(
        notebook_analysis_service, summary_service, orchestration_service, context_service
    )

    return notebook_analysis_service, summary_service, intent_service


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "add", "cell_index": 1}], "dependencies": []}
)
SUMMARY_RESPONSE = json.dumps(
    {
        "purpose": "Adds two numbers.",
        "key_components": [{"name": "add", "description": "Adds two numbers."}],
        "inputs": ["two numbers"],
        "outputs": ["their sum"],
        "dependencies": [],
    }
)

SMALLER_NOTEBOOK = {"notebook_id": "nb-1", "cells": [{"cell_type": "markdown", "source": "# Intro"}]}
SMALLER_ANALYSIS_RESPONSE = json.dumps({"imports": [], "functions": [], "dependencies": []})

INTENT_RESPONSE = json.dumps(
    {
        "operations": [{"operation": "expose add as an endpoint", "function": "add", "ambiguous": False}],
        "candidate_functions": ["add"],
        "requested_exposure": "PUBLIC",
        "constraints": ["no auth required"],
        "confidence": 0.85,
    }
)
AMBIGUOUS_INTENT_RESPONSE = json.dumps(
    {
        "operations": [
            {"operation": "expose some numeric operation", "function": None, "ambiguous": True}
        ],
        "candidate_functions": ["add"],
        "requested_exposure": "UNSPECIFIED",
        "constraints": [],
        "confidence": 0.4,
    }
)
GUESSED_AMBIGUOUS_RESPONSE = json.dumps(
    {
        "operations": [{"operation": "guess anyway", "function": "add", "ambiguous": True}],
        "candidate_functions": [],
        "requested_exposure": "UNSPECIFIED",
        "constraints": [],
        "confidence": 0.3,
    }
)
UNKNOWN_FUNCTION_RESPONSE = json.dumps(
    {
        "operations": [{"operation": "expose subtract", "function": "subtract", "ambiguous": False}],
        "candidate_functions": [],
        "requested_exposure": "PUBLIC",
        "constraints": [],
        "confidence": 0.5,
    }
)


def test_intent_extraction_is_grounded_in_analysis_and_summary():
    notebook_analysis, summary_service, intent_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(SUMMARY_RESPONSE), make_response(INTENT_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)
    summary_service.summarize("nb-1")

    intent = intent_service.extract("nb-1")

    assert intent.notebook_id == "nb-1"
    assert intent.operations == [
        {"operation": "expose add as an endpoint", "function": "add", "ambiguous": False}
    ]
    assert intent.candidate_functions == ["add"]
    assert intent.requested_exposure == "PUBLIC"
    assert intent.constraints == ["no auth required"]
    assert intent.confidence == 0.85
    assert intent_service.get("nb-1") == intent


def test_function_mapping_rejects_unknown_functions():
    notebook_analysis, _summary_service, intent_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(UNKNOWN_FUNCTION_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)

    with pytest.raises(UnknownIntentFunctionError):
        intent_service.extract("nb-1")


def test_ambiguous_operations_must_not_guess_a_function():
    notebook_analysis, _summary_service, intent_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(AMBIGUOUS_INTENT_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)

    intent = intent_service.extract("nb-1")

    assert intent.operations[0]["ambiguous"] is True
    assert intent.operations[0]["function"] is None


def test_an_ambiguous_operation_that_still_guesses_is_rejected():
    notebook_analysis, _summary_service, intent_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(GUESSED_AMBIGUOUS_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)

    with pytest.raises(MalformedIntentResponseError):
        intent_service.extract("nb-1")


def test_malformed_json_response_is_rejected():
    notebook_analysis, _summary_service, intent_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response("not json")]
    )
    notebook_analysis.analyze(NOTEBOOK)

    with pytest.raises(MalformedIntentResponseError):
        intent_service.extract("nb-1")


def test_validate_detects_functions_removed_since_extraction():
    notebook_analysis, _summary_service, intent_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(INTENT_RESPONSE), make_response(SMALLER_ANALYSIS_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)
    intent = intent_service.extract("nb-1")

    assert intent_service.validate(intent) is True

    notebook_analysis.analyze(SMALLER_NOTEBOOK)

    with pytest.raises(UnknownIntentFunctionError):
        intent_service.validate(intent)


def test_extraction_reuses_the_existing_analysis_without_a_summary():
    notebook_analysis, _summary_service, intent_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(INTENT_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)
    # Deliberately never generated a Commit #2 summary.

    intent = intent_service.extract("nb-1")

    assert intent.candidate_functions == ["add"]

    _analysis, _summary, fresh_intent_service = build_env([])
    with pytest.raises(UnknownAnalysisError):
        fresh_intent_service.extract("nb-never-analyzed")


def test_extraction_never_mutates_notebook_source():
    notebook_analysis, summary_service, intent_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(SUMMARY_RESPONSE), make_response(INTENT_RESPONSE)]
    )
    analysis = notebook_analysis.analyze(NOTEBOOK)
    summary_service.summarize("nb-1")
    original_sources = [cell.source for cell in analysis.cells]

    intent_service.extract("nb-1")

    current = notebook_analysis.get_by_notebook("nb-1")
    assert [cell.source for cell in current.cells] == original_sources
    assert current is analysis
