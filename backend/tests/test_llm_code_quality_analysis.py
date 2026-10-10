import json

import pytest

from backend.code_quality import LLMCodeQualityService, MalformedFindingError
from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService


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
    quality_service = LLMCodeQualityService(notebook_analysis_service, orchestration_service, context_service)

    return notebook_analysis_service, quality_service


NOTEBOOK = {
    "notebook_id": "nb-1",
    "cells": [
        {"cell_type": "markdown", "source": "# Intro"},
        {"cell_type": "code", "source": "def divide(a, b):\n    return a / b"},
        {"cell_type": "code", "source": "x = 1\nx = 2"},
    ],
}
ANALYSIS_RESPONSE = json.dumps(
    {"imports": [], "functions": [{"name": "divide", "cell_index": 1}], "dependencies": []}
)


def finding_entry(cell_id, category, severity, message="issue found", confidence=0.8):
    return {
        "cell_id": cell_id,
        "category": category,
        "severity": severity,
        "message": message,
        "confidence": confidence,
    }


FINDINGS_RESPONSE = json.dumps(
    {
        "findings": [
            finding_entry("cell:1", "BUG", "ERROR", "possible ZeroDivisionError when b is 0"),
            finding_entry("cell:2", "DEAD_CODE", "INFO", "x is reassigned before use"),
            finding_entry("cell:2", "SMELL", "WARNING", "redundant reassignment"),
        ]
    }
)


def run_analysis(findings_response=FINDINGS_RESPONSE):
    notebook_analysis_service, quality_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(findings_response)]
    )
    analysis = notebook_analysis_service.analyze(NOTEBOOK)
    findings = quality_service.analyze(analysis.analysis_id)
    return notebook_analysis_service, quality_service, analysis, findings


def test_finding_generation():
    _, quality_service, analysis, findings = run_analysis()

    assert len(findings) == 3
    assert quality_service.findings(analysis.notebook_id) == findings


@pytest.mark.parametrize(
    "bad_response",
    [
        json.dumps({"findings": [finding_entry("cell:1", "TYPO", "ERROR")]}),
        json.dumps({"findings": [finding_entry("cell:1", "BUG", "CRITICAL")]}),
    ],
)
def test_category_severity_validation(bad_response):
    with pytest.raises(MalformedFindingError):
        run_analysis(bad_response)


def test_cell_references():
    with pytest.raises(MalformedFindingError):
        run_analysis(json.dumps({"findings": [finding_entry("cell:99", "BUG", "ERROR")]}))

    _, _, analysis, findings = run_analysis()
    assert findings[0].cell_id == "cell:1"
    referenced_index = int(findings[0].cell_id.split(":")[1])
    assert analysis.cells[referenced_index].source == "def divide(a, b):\n    return a / b"


def test_critical_filtering():
    _, quality_service, analysis, findings = run_analysis()

    critical = quality_service.critical(analysis.notebook_id)

    assert len(critical) == 1
    assert critical[0].severity == "ERROR"
    assert critical[0].category == "BUG"


@pytest.mark.parametrize(
    "bad_response",
    [
        "there is a bug in cell 1",
        json.dumps({"issues": []}),
        json.dumps({"findings": [{"cell_id": "cell:1", "category": "BUG", "severity": "ERROR"}]}),
        json.dumps({"findings": [finding_entry("cell:1", "BUG", "ERROR", confidence=1.5)]}),
        json.dumps({"findings": [finding_entry("cell:1", "BUG", "ERROR", confidence="high")]}),
    ],
)
def test_malformed_finding_rejection(bad_response):
    with pytest.raises(MalformedFindingError):
        run_analysis(bad_response)


def test_source_preservation():
    notebook_analysis_service, _, analysis, _ = run_analysis()

    stored = notebook_analysis_service.get(analysis.analysis_id)

    assert [c.source for c in stored.cells] == [c["source"] for c in NOTEBOOK["cells"]]
    assert [c.cell_type for c in stored.cells] == [c["cell_type"] for c in NOTEBOOK["cells"]]
