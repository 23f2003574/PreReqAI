import json

import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService, UnknownAnalysisError
from backend.notebook_summary import (
    LLMNotebookSummaryService,
    MalformedSummaryResponseError,
    UnknownSummaryError,
)


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

    return notebook_analysis_service, summary_service


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "code", "source": "import math"},
        {"cell_type": "code", "source": "def add(a, b):\n    return a + b"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {"imports": ["import math"], "functions": [{"name": "add", "cell_index": 1}], "dependencies": ["math"]}
)
SUMMARY_RESPONSE = json.dumps(
    {
        "purpose": "Provides a simple addition utility.",
        "key_components": [{"name": "add", "description": "Adds two numbers together."}],
        "inputs": ["two numbers"],
        "outputs": ["their sum"],
        "dependencies": ["math"],
    }
)

MINIMAL_NOTEBOOK = {"notebook_id": "nb-2", "cells": [{"cell_type": "markdown", "source": "# Just notes"}]}
MINIMAL_ANALYSIS_RESPONSE = json.dumps({"imports": [], "functions": [], "dependencies": []})
MINIMAL_SUMMARY_RESPONSE = json.dumps(
    {
        "purpose": "A notes-only notebook with no executable code.",
        "key_components": [],
        "inputs": [],
        "outputs": [],
        "dependencies": [],
    }
)


def test_summary_generation_is_grounded_in_the_parsed_analysis():
    notebook_analysis, summary_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(SUMMARY_RESPONSE)]
    )
    notebook_analysis.analyze(NOTEBOOK)

    summary = summary_service.summarize("nb-1")

    assert summary.notebook_id == "nb-1"
    assert summary.purpose == "Provides a simple addition utility."
    assert summary.key_components == [{"name": "add", "description": "Adds two numbers together."}]
    assert summary.inputs == ["two numbers"]
    assert summary.outputs == ["their sum"]
    assert summary.dependencies == ["math"]
    assert summary.generated_at is not None

    assert summary_service.get_summary("nb-1") == summary


def test_empty_minimal_notebook_produces_a_valid_empty_summary():
    notebook_analysis, summary_service = build_env(
        [make_response(MINIMAL_ANALYSIS_RESPONSE), make_response(MINIMAL_SUMMARY_RESPONSE)]
    )
    notebook_analysis.analyze(MINIMAL_NOTEBOOK)

    summary = summary_service.summarize("nb-2")

    assert summary.key_components == []
    assert summary.inputs == []
    assert summary.outputs == []
    assert summary.dependencies == []


def test_malformed_json_response_is_rejected():
    notebook_analysis, summary_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response("not json")]
    )
    notebook_analysis.analyze(NOTEBOOK)

    with pytest.raises(MalformedSummaryResponseError):
        summary_service.summarize("nb-1")


@pytest.mark.parametrize(
    "bad_response",
    [
        json.dumps({"purpose": "Adds numbers.", "key_components": [], "inputs": [], "outputs": []}),
        json.dumps(
            {
                "purpose": "Adds numbers.",
                "key_components": [{"name": "subtract", "description": "Not real."}],
                "inputs": [],
                "outputs": [],
                "dependencies": [],
            }
        ),
        json.dumps(
            {
                "purpose": "Adds numbers.",
                "key_components": [],
                "inputs": [],
                "outputs": [],
                "dependencies": ["numpy"],
            }
        ),
        json.dumps(
            {"purpose": "", "key_components": [], "inputs": [], "outputs": [], "dependencies": []}
        ),
    ],
)
def test_structured_response_is_validated(bad_response):
    notebook_analysis, summary_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(bad_response)]
    )
    notebook_analysis.analyze(NOTEBOOK)

    with pytest.raises(MalformedSummaryResponseError):
        summary_service.summarize("nb-1")


def test_summarize_reuses_the_existing_parser_and_never_reparses_itself():
    _notebook_analysis, summary_service = build_env([make_response(SUMMARY_RESPONSE)])

    with pytest.raises(UnknownAnalysisError):
        summary_service.summarize("nb-never-analyzed")


def test_summarizing_never_mutates_notebook_source():
    notebook_analysis, summary_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(SUMMARY_RESPONSE)]
    )
    analysis = notebook_analysis.analyze(NOTEBOOK)
    original_sources = [cell.source for cell in analysis.cells]

    summary_service.summarize("nb-1")

    current = notebook_analysis.get_by_notebook("nb-1")
    assert [cell.source for cell in current.cells] == original_sources
    assert current is analysis


def test_get_summary_before_summarize_raises():
    _notebook_analysis, summary_service = build_env([])

    with pytest.raises(UnknownSummaryError):
        summary_service.get_summary("nb-never-summarized")
