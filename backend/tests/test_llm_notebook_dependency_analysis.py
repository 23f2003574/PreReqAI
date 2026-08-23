import json

import pytest

from backend.llm import LLMProvider, LLMResponse
from backend.llm.config import LLMProviderConfig, LLMProviderConfigService
from backend.llm.context import LLMContextService
from backend.llm.orchestration import LLMRequestOrchestrationService
from backend.llm.routing import LLMModelRoutingService, ProviderCapabilityProfile
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_dependencies import (
    CyclicDependencyError,
    LLMNotebookDependencyService,
    MalformedDependencyResponseError,
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
    dependency_service = LLMNotebookDependencyService(
        notebook_analysis_service, orchestration_service, context_service
    )

    return notebook_analysis_service, dependency_service


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

VALID_EDGES = [
    {"source": "cell:1", "target": "import:0", "dependency_type": "IMPORT", "confidence": 0.95},
    {"source": "cell:1", "target": "import:1", "dependency_type": "IMPORT", "confidence": 0.9},
    {"source": "cell:3", "target": "function:add", "dependency_type": "FUNCTION", "confidence": 0.99},
]
DEPENDENCY_RESPONSE = json.dumps({"edges": VALID_EDGES})


def analyze_notebook_and_dependencies(dependency_response):
    notebook_analysis_service, dependency_service = build_env(
        [make_response(ANALYSIS_RESPONSE), make_response(dependency_response)]
    )
    analysis = notebook_analysis_service.analyze(NOTEBOOK)
    dependencies = dependency_service.analyze(analysis.analysis_id)
    return dependency_service, dependencies


def test_dependency_extraction():
    dependency_service, dependencies = analyze_notebook_and_dependencies(DEPENDENCY_RESPONSE)

    assert len(dependencies) == 3
    assert dependency_service.dependencies("nb-1") == dependencies
    assert {dep.dependency_type for dep in dependencies} == {"IMPORT", "FUNCTION"}


def test_direction_is_preserved():
    dependency_service, dependencies = analyze_notebook_and_dependencies(DEPENDENCY_RESPONSE)

    import_edge = next(dep for dep in dependencies if dep.dependency_type == "FUNCTION")
    assert import_edge.source == "nb-1::cell:3"
    assert import_edge.target == "nb-1::function:add"

    downstream_of_cell3 = dependency_service.downstream("nb-1::cell:3")
    assert [dep.target for dep in downstream_of_cell3] == ["nb-1::function:add"]

    upstream_of_function = dependency_service.upstream("nb-1::function:add")
    assert [dep.source for dep in upstream_of_function] == ["nb-1::cell:3"]


def test_upstream_downstream_lookup():
    dependency_service, _ = analyze_notebook_and_dependencies(DEPENDENCY_RESPONSE)

    downstream_of_cell1 = {dep.target for dep in dependency_service.downstream("nb-1::cell:1")}
    assert downstream_of_cell1 == {"nb-1::import:0", "nb-1::import:1"}

    assert dependency_service.upstream("nb-1::cell:1") == []
    assert dependency_service.downstream("nb-1::not-a-real-node") == []
    assert dependency_service.upstream("nb-1::not-a-real-node") == []


@pytest.mark.parametrize(
    "raw_content",
    [
        "cell 1 imports numpy and pandas",
        json.dumps({"nodes": []}),
        json.dumps({"edges": [{"source": "cell:1", "target": "import:0", "dependency_type": "IMPORT"}]}),
        json.dumps(
            {"edges": [{"source": "cell:1", "target": "import:0", "dependency_type": "IMPORTS", "confidence": 0.5}]}
        ),
        json.dumps(
            {"edges": [{"source": "cell:99", "target": "import:0", "dependency_type": "IMPORT", "confidence": 0.5}]}
        ),
        json.dumps(
            {
                "edges": [
                    {
                        "source": "cell:1",
                        "target": "function:does_not_exist",
                        "dependency_type": "FUNCTION",
                        "confidence": 0.5,
                    }
                ]
            }
        ),
    ],
)
def test_malformed_dependency_response_is_rejected(raw_content):
    with pytest.raises(MalformedDependencyResponseError):
        analyze_notebook_and_dependencies(raw_content)


def test_type_validation():
    with pytest.raises(MalformedDependencyResponseError):
        analyze_notebook_and_dependencies(
            json.dumps(
                {"edges": [{"source": "cell:1", "target": "import:0", "dependency_type": "OTHER", "confidence": 0.5}]}
            )
        )


@pytest.mark.parametrize("bad_confidence", [-0.1, 1.1, "high"])
def test_confidence_validation(bad_confidence):
    with pytest.raises(MalformedDependencyResponseError):
        analyze_notebook_and_dependencies(
            json.dumps(
                {
                    "edges": [
                        {
                            "source": "cell:1",
                            "target": "import:0",
                            "dependency_type": "IMPORT",
                            "confidence": bad_confidence,
                        }
                    ]
                }
            )
        )


def test_cycle_detection():
    cyclic_response = json.dumps(
        {
            "edges": [
                {"source": "cell:1", "target": "cell:3", "dependency_type": "DATA", "confidence": 0.6},
                {"source": "cell:3", "target": "cell:1", "dependency_type": "DATA", "confidence": 0.6},
            ]
        }
    )

    with pytest.raises(CyclicDependencyError):
        analyze_notebook_and_dependencies(cyclic_response)


def test_self_loop_is_a_cycle():
    self_loop_response = json.dumps(
        {"edges": [{"source": "cell:1", "target": "cell:1", "dependency_type": "DATA", "confidence": 0.6}]}
    )

    with pytest.raises(CyclicDependencyError):
        analyze_notebook_and_dependencies(self_loop_response)
